from django.contrib import admin
from .models import Contrat


@admin.register(Contrat)
class ContratAdmin(admin.ModelAdmin):
    # Champs affichés dans la liste des contrats
    list_display = (
        "id",
        "bien",
        "locataire",
        "type_contrat",
        "date_debut",
        "date_fin",
        "loyer",
        "prix",
        "depot_garantie",
        "statut",
        "date_creation",
    )

    # Filtres latéraux
    list_filter = ("statut", "type_contrat", "date_debut", "date_fin")

    # Champs de recherche
    search_fields = ("bien__adresse", "bien__titre", "locataire__user__nom", "locataire__user__prenoms")

    # Champs en lecture seule
    readonly_fields = ("date_creation",)

    # Champs avec sélection en raw_id (pour optimiser les performances)
    raw_id_fields = ("bien", "locataire")

    # Hiérarchie des dates
    date_hierarchy = "date_creation"

    # Ordre par défaut
    ordering = ("-date_creation",)

    # Organisation des champs dans le formulaire d'édition (fieldsets)
    fieldsets = (
        (None, {
            "fields": ("bien", "locataire", "type_contrat", "statut")
        }),
        ("Période", {
            "fields": ("date_debut", "date_fin")
        }),
        ("Montants", {
            "fields": ("loyer", "depot_garantie", "prix")
        }),
        ("Documents", {
            "fields": ("document_pdf",)
        }),
        ("Métadonnées", {
            "fields": ("date_creation",)
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        """
        Pour un contrat existant, on bloque la modification des champs critiques
        (bien, locataire, type_contrat) afin d'éviter des incohérences.
        """
        if obj:  # Modification d'un contrat existant
            return self.readonly_fields + ("bien", "locataire", "type_contrat")
        return self.readonly_fields

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        """
        Ajout de messages d'aide (help_text) pour guider l'utilisateur
        sur les règles métier.
        """
        if db_field.name == "type_contrat":
            kwargs["help_text"] = "Choisissez LOCATION pour une location, ACHAT pour une vente."
        elif db_field.name == "loyer":
            kwargs["help_text"] = "Obligatoire pour une location, ignoré pour un achat."
        elif db_field.name == "depot_garantie":
            kwargs["help_text"] = "Obligatoire pour une location, ignoré pour un achat."
        elif db_field.name == "prix":
            kwargs["help_text"] = "Obligatoire pour un achat, ignoré pour une location."
        elif db_field.name == "statut":
            kwargs["help_text"] = (
                "Pour une location : ACTIF, RESILIE, TERMINE. "
                "Pour un achat : ACTIF, VENDU."
            )
        return super().formfield_for_dbfield(db_field, request, **kwargs)