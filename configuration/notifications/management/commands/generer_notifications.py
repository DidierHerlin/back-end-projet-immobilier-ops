# immobilier/management/commands/generer_notifications.py

"""
Implémente RG-20 et RG-21.

Planification :
  Linux (crontab -e) :
      0 6 * * * cd /chemin/projet && /chemin/venv/bin/python manage.py generer_notifications

  Windows (Planificateur de tâches) :
      Programme : C:\\...\\venv\\Scripts\\python.exe
      Arguments : manage.py generer_notifications
      Dossier de démarrage : C:\\...\\Configuration

Test manuel :
    python manage.py generer_notifications
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from models import Notification


class Command(BaseCommand):
    help = "Génère les notifications d'échéance (RG-20) et de retard (RG-21)."

    def handle(self, *args, **options):
        aujourdhui = timezone.now().date()
        total_echeance = 0
        total_retard = 0

        # --- RG-20 : échéance de loyer dans exactement 5 jours ---------------
        date_cible = aujourdhui + timedelta(days=5)
        paiements_a_venir = Paiement.objects.filter(
            date_echeance=date_cible,
            statut=Paiement.Statut.EN_ATTENTE,
        ).select_related("contrat__locataire__utilisateur")

        for paiement in paiements_a_venir:
            utilisateur = getattr(paiement.contrat.locataire, "utilisateur", None)
            if utilisateur is None:
                continue

            deja_envoyee = Notification.objects.filter(
                utilisateur=utilisateur,
                type=Notification.Type.ECHEANCE_LOYER,
                message__contains=f"Paiement #{paiement.id}",
            ).exists()
            if deja_envoyee:
                continue

            Notification.objects.create(
                utilisateur=utilisateur,
                type=Notification.Type.ECHEANCE_LOYER,
                message=(
                    f"Paiement #{paiement.id} — Votre loyer de "
                    f"{paiement.montant} est à régler le "
                    f"{paiement.date_echeance.strftime('%d/%m/%Y')}."
                ),
            )
            total_echeance += 1

        # --- RG-21 : retard détecté (> 5 jours après échéance, RG-15) --------
        limite_retard = aujourdhui - timedelta(days=5)
        paiements_en_retard = Paiement.objects.filter(
            date_echeance__lt=limite_retard,
            statut__in=[Paiement.Statut.EN_ATTENTE, Paiement.Statut.EN_RETARD],
        ).select_related("contrat__locataire__utilisateur")

        for paiement in paiements_en_retard:
            if paiement.statut != Paiement.Statut.EN_RETARD:
                paiement.statut = Paiement.Statut.EN_RETARD
                paiement.save(update_fields=["statut"])

            utilisateur = getattr(paiement.contrat.locataire, "utilisateur", None)
            if utilisateur is None:
                continue

            deja_envoyee = Notification.objects.filter(
                utilisateur=utilisateur,
                type=Notification.Type.RETARD_PAIEMENT,
                message__contains=f"Paiement #{paiement.id}",
            ).exists()
            if deja_envoyee:
                continue

            Notification.objects.create(
                utilisateur=utilisateur,
                type=Notification.Type.RETARD_PAIEMENT,
                message=(
                    f"Paiement #{paiement.id} — Votre loyer de "
                    f"{paiement.montant}, échu le "
                    f"{paiement.date_echeance.strftime('%d/%m/%Y')}, "
                    f"est en retard."
                ),
            )
            total_retard += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Terminé : {total_echeance} notification(s) d'échéance (RG-20), "
                f"{total_retard} notification(s) de retard (RG-21)."
            )
        )