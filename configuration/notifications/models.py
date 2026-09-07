import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


class Notification(models.Model):
    """Table NOTIFICATION du MLD."""

    class Type(models.TextChoices):
        ECHEANCE_LOYER = "ECHEANCE_LOYER", "Échéance de loyer"
        FIN_CONTRAT = "FIN_CONTRAT", "Fin de contrat"
        RETARD_PAIEMENT = "RETARD_PAIEMENT", "Retard de paiement"
        AUTRE = "AUTRE", "Autre"

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="utilisateur",
    )
    type = models.CharField(
        "type", max_length=30, choices=Type.choices, default=Type.AUTRE,
    )
    message = models.TextField("message")
    date = models.DateTimeField("date", auto_now_add=True)
    lu = models.BooleanField("lu", default=False)
    email_envoye = models.BooleanField(
        "email envoyé",
        default=False,
        help_text="Indique si l'email associé à cette notification a été envoyé avec succès.",
    )

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["utilisateur", "lu"]),
        ]

    def __str__(self):
        return f"[{self.get_type_display()}] → {self.utilisateur.email} ({self.date:%d/%m/%Y %H:%M})"


@receiver(post_save, sender=Notification)
def envoyer_email_notification(sender, instance: Notification, created, **kwargs):
    """
    Envoie automatiquement un email à chaque création de notification
    (module 4.8 : "notification par email et/ou dans l'application").
    Ne s'exécute qu'à la CRÉATION, jamais lors d'un update (ex: marquer lu).
    """
    if not created:
        return

    destinataire = instance.utilisateur.email
    if not destinataire:
        return

    try:
        nb_envoyes = send_mail(
            subject=f"[Gestion Immobilière] {instance.get_type_display()}",
            message=instance.message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[destinataire],
            fail_silently=False,
        )
        if nb_envoyes > 0:
            # update() évite de redéclencher ce signal (pas de save())
            Notification.objects.filter(pk=instance.pk).update(email_envoye=True)
    except Exception:
        logger.exception(
            "Échec de l'envoi de l'email pour la notification #%s", instance.pk
        )