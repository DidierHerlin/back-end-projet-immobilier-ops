"""
Validateurs réutilisables pour le module Contrat.

Ces fonctions sont volontairement indépendantes de Django REST Framework
et du modèle : elles sont appelées à la fois par Contrat.clean() (validation
au niveau modèle / admin / shell) et par ContratSerializer.validate()
(validation au niveau API), afin de ne jamais dupliquer la règle de gestion
à deux endroits différents.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError


def valider_dates_contrat(date_debut, date_fin):
    """
    RG-12 : la date de fin doit être strictement postérieure à la date de début.
    Traduite en CHECK constraint SQL native (voir Contrat.Meta.constraints),
    mais revalidée ici pour renvoyer un message d'erreur clair côté
    application avant même d'atteindre la base de données.
    """
    if date_debut is None or date_fin is None:
        return
    if date_fin <= date_debut:
        raise DjangoValidationError(
            "La date de fin doit être strictement postérieure à la date de début.",
            code="rg12_date_fin_invalide",
        )


def valider_montant_positif(valeur: Decimal, nom_champ: str = "Le montant"):
    """
    Contrainte générique de positivité (loyer >= 0, depot_garantie >= 0).
    """
    if valeur is not None and valeur < 0:
        raise DjangoValidationError(
            f"{nom_champ} ne peut pas être négatif.",
            code="montant_negatif",
        )


def valider_unicite_contrat_actif(bien_id, statut, contrat_pk=None, *, queryset):
    """
    RG-13 : un bien ne peut être associé qu'à un seul contrat ACTIF à la fois.

    Cette fonction fait la même vérification que l'index unique partiel
    posé en base (voir Contrat.Meta.constraints), mais permet de renvoyer
    une erreur de validation propre (400) plutôt qu'une IntegrityError (500)
    lorsque la requête passe par le serializer/formulaire.

    `queryset` est injecté par l'appelant pour éviter tout import circulaire
    avec le modèle Contrat.
    """
    from .models import Contrat  # import local pour éviter le cycle modèle <-> validators

    if statut != Contrat.Statut.ACTIF:
        return

    conflits = queryset.filter(bien_id=bien_id, statut=Contrat.Statut.ACTIF)
    if contrat_pk is not None:
        conflits = conflits.exclude(pk=contrat_pk)

    if conflits.exists():
        raise DjangoValidationError(
            "Ce bien possède déjà un contrat ACTIF en cours. "
            "Il doit être résilié ou terminé avant d'en créer un nouveau.",
            code="rg13_contrat_actif_existant",
        )