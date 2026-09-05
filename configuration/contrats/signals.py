import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from bien.models import Bien
from .models import Contrat

logger = logging.getLogger(__name__)


def mettre_a_jour_statut_bien(bien):
    if bien.statut == Bien.StatutBien.VENDU:
        return
    a_un_contrat_actif = Contrat.objects.filter(
        bien=bien, statut=Contrat.StatutContrat.ACTIF
    ).exists()
    if a_un_contrat_actif:
        nouveau_statut = Bien.StatutBien.LOUE
    else:
        if bien.statut != Bien.StatutBien.EN_TRAVAUX:
            nouveau_statut = Bien.StatutBien.DISPONIBLE
        else:
            nouveau_statut = bien.statut
    if bien.statut != nouveau_statut:
        bien.statut = nouveau_statut
        bien.save(update_fields=["statut"])
        logger.info("Bien #%s -> %s (mise à jour après contrat)", bien.pk, nouveau_statut)


@receiver(post_save, sender=Contrat)
def synchroniser_bien_apres_sauvegarde_contrat(sender, instance: Contrat, **kwargs):
    bien = instance.bien
    if bien.statut == Bien.StatutBien.VENDU:
        return
    if instance.type_contrat == Contrat.TypeContrat.LOCATION:
        if instance.statut == Contrat.StatutContrat.ACTIF:
            if bien.statut != Bien.StatutBien.LOUE:
                bien.statut = Bien.StatutBien.LOUE
                bien.save(update_fields=["statut"])
                logger.info("Bien #%s -> LOUE (contrat actif #%s)", bien.pk, instance.pk)
        elif instance.statut in (Contrat.StatutContrat.RESILIE, Contrat.StatutContrat.TERMINE):
            mettre_a_jour_statut_bien(bien)
    elif instance.type_contrat == Contrat.TypeContrat.ACHAT:
        if instance.statut == Contrat.StatutContrat.VENDU:
            if bien.statut != Bien.StatutBien.VENDU:
                bien.statut = Bien.StatutBien.VENDU
                bien.save(update_fields=["statut"])
                logger.info("Bien #%s -> VENDU (vente finalisée #%s)", bien.pk, instance.pk)


@receiver(post_delete, sender=Contrat)
def synchroniser_bien_apres_suppression_contrat(sender, instance: Contrat, **kwargs):
    mettre_a_jour_statut_bien(instance.bien)