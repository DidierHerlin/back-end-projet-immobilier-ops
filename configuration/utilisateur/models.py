
import os

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

# FONCTION POUR LE CHEMIN DE LA PHOTO
def photo_profil_upload_path(instance, filename):
    """
    Génère un chemin personnalisé pour les photos de profil.
    """
    ext = filename.split(".")[-1]
    filename = f"photo_{instance.pk}.{ext}"
    return os.path.join("profils", f"utilisateur_{instance.pk}", filename)

# Gestion utilisateurs
class UtilisateurManager(BaseUserManager):
    """
    Manager personnalisé permettant l'authentification par email
    """
    ROLES_AUTO_ACTIFS = ["LOCATAIRE", "PROPRIETAIRE", "AGENT"]

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("L'adresse email est obligatoire.")
        email = self.normalize_email(email)
        role = extra_fields.get("role", Utilisateur.Role.LOCATAIRE)
        extra_fields.setdefault("is_active", role in self.ROLES_AUTO_ACTIFS)
        photo_profil = extra_fields.pop("photo_profil", None)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        if photo_profil:
            user.photo_profil = photo_profil
            user.save(using=self._db, update_fields=["photo_profil"])

        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", Utilisateur.Role.ADMIN)
        extra_fields.setdefault("is_active", True)  # un superuser est toujours actif
        return self.create_user(email, password, **extra_fields)


#Model utilisateur
class Utilisateur(AbstractBaseUser, PermissionsMixin):

    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Administrateur"
        AGENT = "AGENT", "Agent immobilier"
        PROPRIETAIRE = "PROPRIETAIRE", "Propriétaire"
        LOCATAIRE = "LOCATAIRE", "Locataire"

    email = models.EmailField("adresse email", unique=True)
    nom = models.CharField("nom", max_length=100)
    prenoms = models.CharField("prénoms", max_length=150)
    role = models.CharField(
        "rôle", max_length=20, choices=Role.choices, default=Role.LOCATAIRE
    )
    telephone = models.CharField("téléphone", max_length=30, blank=True, null=True)

    # PHOTO DE PROFIL
    photo_profil = models.ImageField(
        "photo de profil",
        upload_to=photo_profil_upload_path,
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=["jpg", "jpeg", "png", "gif"])],
        help_text="Photo de profil (optionnel). Formats acceptés : JPG, PNG, GIF",
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    date_creation = models.DateTimeField("date de création", auto_now_add=True)

    # RÉINITIALISATION DE MOT DE PASSE
    reset_token = models.CharField(max_length=10, blank=True, null=True)
    reset_token_expiration = models.DateTimeField(blank=True, null=True)
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nom", "prenoms", "role"]

    objects = UtilisateurManager()

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"
        ordering = ["-date_creation"]

    def __str__(self):
        return f"{self.nom} {self.prenoms} ({self.get_role_display()})"

    def get_full_name(self):
        return f"{self.prenoms} {self.nom}".strip()

    def get_short_name(self):
        return self.prenoms

    def get_photo_url(self):
        if self.photo_profil:
            return self.photo_profil.url
        return None

    def has_photo(self):
        return bool(self.photo_profil)

# SIGNAL : DROITS ADMIN AUTOMATIQUES 
@receiver(pre_save, sender=Utilisateur)
def rendre_admin_complet(sender, instance, **kwargs):
    """Seuls les comptes 'ADMIN' ont les droits admin Django (staff + superuser)."""
    if instance.role == Utilisateur.Role.ADMIN:
        instance.is_staff = True
        instance.is_superuser = True


@receiver(post_save, sender=Utilisateur)
def log_creation_admin(sender, instance, created, **kwargs):
    if created and instance.role == Utilisateur.Role.ADMIN:
        print(f"\n✅ ADMINISTRATEUR CRÉÉ → {instance.email} | Accès admin activé !\n")


# ====================== SIGNAL : SUPPRESSION DE L'ANCIENNE PHOTO ======================
@receiver(pre_save, sender=Utilisateur)
def delete_old_profile_photo(sender, instance, **kwargs):
    if not instance.pk:
        return False

    try:
        ancien_utilisateur = Utilisateur.objects.get(pk=instance.pk)
    except Utilisateur.DoesNotExist:
        return False

    if ancien_utilisateur.photo_profil and ancien_utilisateur.photo_profil != instance.photo_profil:
        if os.path.isfile(ancien_utilisateur.photo_profil.path):
            os.remove(ancien_utilisateur.photo_profil.path)


# ====================== PROFIL PROPRIÉTAIRE ======================
class Proprietaire(models.Model):
 
    user = models.OneToOneField(
        Utilisateur, on_delete=models.CASCADE, related_name="profil_proprietaire"
    )
    iban = models.CharField("IBAN", max_length=34)
    contact = models.CharField("contact", max_length=20, blank=True, null=True)

    class Meta:
        verbose_name = "Propriétaire"
        verbose_name_plural = "Propriétaires"

    def __str__(self):
        return f"Propriétaire - {self.user.nom} {self.user.prenoms}"

    def get_photo_url(self):
        """Raccourci pour accéder à la photo via le profil propriétaire."""
        return self.user.get_photo_url()

# ====================== PROFIL LOCATAIRE ======================
class Locataire(models.Model):
    user = models.OneToOneField(
        Utilisateur, on_delete=models.CASCADE, related_name="profil_locataire"
    )
    piece_identite = models.FileField(
        "pièce d'identité",
        upload_to="locataires/pieces_identite/",
        blank=True,
        null=True,
    )
    contact = models.CharField("contact", max_length=20, blank=True, null=True)

    class Meta:
        verbose_name = "Locataire"
        verbose_name_plural = "Locataires"

    def __str__(self):
        return f"Locataire - {self.user.nom} {self.user.prenoms}"

    def get_photo_url(self):
        return self.user.get_photo_url()