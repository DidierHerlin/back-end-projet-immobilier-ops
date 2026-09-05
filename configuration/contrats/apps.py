from django.apps import AppConfig


class ContratsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "contrats"  # adaptez au nom réel du module si différent (ex: "contrats.apps.ContratsConfig" dans INSTALLED_APPS)
    verbose_name = "Contrats"

    def ready(self) -> None:
        # Importe le module de signaux pour connecter les @receiver au
        # démarrage de l'application. Ne pas retirer cet import même s'il
        # semble inutilisé : c'est l'import lui-même qui déclenche la
        # connexion des signaux (post_save sur Contrat).
        from . import signals  # noqa: F401