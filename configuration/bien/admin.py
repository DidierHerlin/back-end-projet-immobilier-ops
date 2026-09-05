"""Interface d'administration du module Bien."""

from django.contrib import admin
from .models import Bien


@admin.register(Bien)
class BienAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "titre",
        "type",
        "mode_transaction",
        "statut",
        "loyer_mensuel",
        "prix",
        "surface",
        "nombre_pieces",
        "proprietaire",
    )
    list_filter = ("type", "mode_transaction", "statut")
    search_fields = ("titre", "adresse", "proprietaire__user__email", "proprietaire__user__nom")
    ordering = ("-id",)
    readonly_fields = ("id",)
    autocomplete_fields = ("proprietaire",)

    fieldsets = (
        (None, {
            "fields": ("proprietaire", "titre", "type", "mode_transaction", "statut")
        }),
        ("Localisation et surface", {
            "fields": ("adresse", "surface", "nombre_pieces")
        }),
        ("Tarifs", {
            "fields": ("loyer_mensuel", "prix")
        }),
        ("Photos", {
            "fields": ("photos",)
        }),
        ("Métadonnées", {
            "fields": ("id",)
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        # Pour un bien existant, on peut interdire la modification de certains champs
        # selon le statut (ex: LOUE ou VENDU). Mais cela se fait plutôt dans le
        # serializer; dans l'admin on laisse la flexibilité, mais on peut ajouter
        # des avertissements.
        return self.readonly_fields

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        # Ajout d'aides contextuelles pour l'admin
        if db_field.name == "mode_transaction":
            kwargs["help_text"] = "Choisissez LOCATION pour un bien à louer, VENTE pour un bien à vendre."
        elif db_field.name == "loyer_mensuel":
            kwargs["help_text"] = "Obligatoire pour une location, ignoré pour une vente."
        elif db_field.name == "prix":
            kwargs["help_text"] = "Obligatoire pour une vente, ignoré pour une location."
        elif db_field.name == "nombre_pieces":
            kwargs["help_text"] = "Obligatoire pour Appartement/Maison/Local commercial, non applicable pour un Terrain."
        elif db_field.name == "statut":
            kwargs["help_text"] = (
                "DISPONIBLE : bien libre. "
                "LOUE : attribué automatiquement par un contrat de location actif. "
                "VENDU : attribué automatiquement par un contrat de vente finalisé. "
                "EN_TRAVAUX : utilisation manuelle."
            )
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def get_fieldsets(self, request, obj=None):
        # Adaptation dynamique selon le mode de transaction (pour l'affichage)
        fieldsets = super().get_fieldsets(request, obj)
        if obj and obj.mode_transaction == Bien.ModeTransaction.LOCATION:
            # Mettre en avant le loyer, cacher le prix (mais le champ est déjà présent)
            pass
        elif obj and obj.mode_transaction == Bien.ModeTransaction.VENTE:
            pass
        return fieldsets