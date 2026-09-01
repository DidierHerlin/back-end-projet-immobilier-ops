# utilisateur/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Locataire, Proprietaire, Utilisateur


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    """
    Admin personnalisé : on ne peut pas hériter des fieldsets par défaut
    de UserAdmin (prévus pour AbstractUser + username), donc on les
    redéfinit entièrement avec les champs réels du modèle.
    """

    model = Utilisateur

    list_display = ["email", "nom", "prenoms", "role", "is_active", "is_staff", "date_creation"]
    list_filter = ["role", "is_active", "is_staff"]
    search_fields = ["email", "nom", "prenoms"]
    ordering = ["-date_creation"]
    readonly_fields = ["date_creation"]

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Informations personnelles", {"fields": ("nom", "prenoms", "telephone", "photo_profil")}),
        ("Rôle et permissions", {
            "fields": ("role", "is_active", "is_staff", "is_superuser", "groups", "user_permissions"),
        }),
        ("Dates", {"fields": ("date_creation",)}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "nom", "prenoms", "role", "password1", "password2"),
        }),
    )

    filter_horizontal = ("groups", "user_permissions")


@admin.register(Proprietaire)
class ProprietaireAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "iban", "contact"]
    search_fields = ["user__email", "user__nom", "user__prenoms", "iban"]


@admin.register(Locataire)
class LocataireAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "contact"]
    search_fields = ["user__email", "user__nom", "user__prenoms"]