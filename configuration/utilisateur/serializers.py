import random
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Locataire, Proprietaire, Utilisateur


# ===================================================================
# 1. UTILISATEUR SERIALIZER (avec photo_url, comme l'ancien UserSerializer)
# ===================================================================
class UtilisateurSerializer(serializers.ModelSerializer):
    """Profil complet : consultation et modification (y compris la photo)."""

    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = Utilisateur
        fields = [
            "id", "email", "nom", "prenoms",
            "role", "telephone",
            "photo_profil",  # champ d'upload (write)
            "photo_url",     # URL absolue pour l'affichage (read)
            "is_active", "date_creation",
        ]
        read_only_fields = ["id", "email", "role", "is_active", "date_creation"]
        extra_kwargs = {
            "photo_profil": {"required": False, "write_only": True},
        }
        # email et role : un utilisateur ne doit pas pouvoir se les
        # auto-modifier via /me/. Seul l'admin les change via le CRUD normal.

    def get_photo_url(self, obj):
        """Retourne l'URL absolue de la photo de profil (utile pour le frontend Next.js)."""
        request = self.context.get("request")
        if obj.photo_profil:
            if request:
                return request.build_absolute_uri(obj.photo_profil.url)
            return obj.photo_profil.url
        return None


class UtilisateurSimpleSerializer(serializers.ModelSerializer):
    """Version simplifiée pour les listes (ex : sélection d'un locataire dans un contrat)."""

    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = Utilisateur
        fields = ["id", "email", "nom", "prenoms", "role", "photo_url"]

    def get_photo_url(self, obj):
        request = self.context.get("request")
        if obj.photo_profil:
            if request:
                return request.build_absolute_uri(obj.photo_profil.url)
            return obj.photo_profil.url
        return None


class UtilisateurCreateSerializer(serializers.ModelSerializer):
    """
    Création d'un compte (par l'administrateur — RG-01/02).

    `is_active` est en lecture seule : sa valeur est décidée par
    UtilisateurManager.create_user selon le rôle (voir ROLES_AUTO_ACTIFS),
    mais renvoyée dans la réponse pour indiquer si le compte est
    immédiatement actif (LOCATAIRE) ou en attente de validation
    (AGENT, PROPRIETAIRE — voir action `activer` du ViewSet).
    """

    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = Utilisateur
        fields = [
            "id", "email", "nom", "prenoms",
            "role", "telephone", "password", "is_active",
        ]
        read_only_fields = ["id", "is_active"]

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = Utilisateur.objects.create_user(password=password, **validated_data)
        return user


# ===================================================================
# 2. PROPRIETAIRE SERIALIZER (imbriqué, sur le modèle de l'ancien EtudiantSerializer)
# ===================================================================
class ProprietaireSerializer(serializers.ModelSerializer):
    user = UtilisateurSerializer(read_only=True)

    # Champs write-only pour créer le compte Utilisateur en même temps que le profil
    email = serializers.EmailField(write_only=True)
    nom = serializers.CharField(write_only=True)
    prenoms = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True, min_length=8, validators=[validate_password])
    telephone = serializers.CharField(write_only=True, required=False, allow_blank=True)
    photo_profil = serializers.ImageField(write_only=True, required=False)

    class Meta:
        model = Proprietaire
        fields = [
            "id", "user", "iban", "contact",
            # champs de création
            "email", "nom", "prenoms", "password", "telephone", "photo_profil",
        ]

    def validate_iban(self, value):
        if not value or len(value.strip()) == 0:
            raise serializers.ValidationError("L'IBAN ne peut pas être vide.")
        return value.strip()

    def create(self, validated_data):
        email = validated_data.pop("email")
        nom = validated_data.pop("nom")
        prenoms = validated_data.pop("prenoms")
        password = validated_data.pop("password")
        telephone = validated_data.pop("telephone", "")
        photo_profil = validated_data.pop("photo_profil", None)

        user = Utilisateur.objects.create_user(
            email=email,
            password=password,
            nom=nom,
            prenoms=prenoms,
            role=Utilisateur.Role.PROPRIETAIRE,
            telephone=telephone,
            photo_profil=photo_profil,
        )

        proprietaire = Proprietaire.objects.create(user=user, **validated_data)
        return proprietaire

    def update(self, instance, validated_data):
        # Champs directs du profil propriétaire
        instance.iban = validated_data.get("iban", instance.iban)
        instance.contact = validated_data.get("contact", instance.contact)
        instance.save()

        # Mise à jour de l'utilisateur lié, si des données sont fournies
        user = instance.user
        user.nom = validated_data.get("nom", user.nom)
        user.prenoms = validated_data.get("prenoms", user.prenoms)
        user.email = validated_data.get("email", user.email)
        user.telephone = validated_data.get("telephone", user.telephone)

        if "password" in validated_data:
            user.set_password(validated_data["password"])
        if "photo_profil" in validated_data:
            user.photo_profil = validated_data["photo_profil"]

        user.save()
        return instance


class ProprietaireSimpleSerializer(serializers.ModelSerializer):
    """Version simplifiée pour les listes (ex : filtre des biens par propriétaire)."""

    user = UtilisateurSimpleSerializer(read_only=True)

    class Meta:
        model = Proprietaire
        fields = ["id", "user", "iban", "contact"]


# ===================================================================
# 3. LOCATAIRE SERIALIZER (imbriqué, sur le modèle de l'ancien ScolariteSerializer)
# ===================================================================
class LocataireSerializer(serializers.ModelSerializer):
    user = UtilisateurSerializer(read_only=True)

    email = serializers.EmailField(write_only=True)
    nom = serializers.CharField(write_only=True)
    prenoms = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True, min_length=8, validators=[validate_password])
    telephone = serializers.CharField(write_only=True, required=False, allow_blank=True)
    photo_profil = serializers.ImageField(write_only=True, required=False)

    class Meta:
        model = Locataire
        fields = [
            "id", "user", "piece_identite", "contact",
            # champs de création
            "email", "nom", "prenoms", "password", "telephone", "photo_profil",
        ]

    def create(self, validated_data):
        email = validated_data.pop("email")
        nom = validated_data.pop("nom")
        prenoms = validated_data.pop("prenoms")
        password = validated_data.pop("password")
        telephone = validated_data.pop("telephone", "")
        photo_profil = validated_data.pop("photo_profil", None)

        # RG : un locataire est activé automatiquement à l'inscription (ROLES_AUTO_ACTIFS)
        user = Utilisateur.objects.create_user(
            email=email,
            password=password,
            nom=nom,
            prenoms=prenoms,
            role=Utilisateur.Role.LOCATAIRE,
            telephone=telephone,
            photo_profil=photo_profil,
        )

        locataire = Locataire.objects.create(user=user, **validated_data)
        return locataire

    def update(self, instance, validated_data):
        instance.piece_identite = validated_data.get("piece_identite", instance.piece_identite)
        instance.contact = validated_data.get("contact", instance.contact)
        instance.save()

        user = instance.user
        user.nom = validated_data.get("nom", user.nom)
        user.prenoms = validated_data.get("prenoms", user.prenoms)
        user.email = validated_data.get("email", user.email)
        user.telephone = validated_data.get("telephone", user.telephone)

        if "password" in validated_data:
            user.set_password(validated_data["password"])
        if "photo_profil" in validated_data:
            user.photo_profil = validated_data["photo_profil"]

        user.save()
        return instance


class LocataireSimpleSerializer(serializers.ModelSerializer):
    """Version simplifiée pour les listes (ex : sélection du locataire dans un contrat)."""

    user = UtilisateurSimpleSerializer(read_only=True)

    class Meta:
        model = Locataire
        fields = ["id", "user", "contact"]


# ===================================================================
# 4. MISE À JOUR DE LA PHOTO DE PROFIL SEULE
# ===================================================================
class UpdateProfilePhotoSerializer(serializers.Serializer):
    """Mise à jour de la photo de profil uniquement."""

    photo_profil = serializers.ImageField(required=True)

    def validate_photo_profil(self, value):
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("La taille de l'image ne doit pas dépasser 5 MB.")

        allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/gif"]
        if value.content_type not in allowed_types:
            raise serializers.ValidationError("Format d'image non supporté. Utilisez JPG, PNG ou GIF.")

        return value

    def save(self, **kwargs):
        user = self.context["request"].user
        user.photo_profil = self.validated_data["photo_profil"]
        user.save(update_fields=["photo_profil"])
        return user


# ===================================================================
# 5. MISE À JOUR DU PROFIL UTILISATEUR (avec changement de mot de passe sécurisé)
# ===================================================================
class UtilisateurUpdateSerializer(serializers.ModelSerializer):
    """
    Mise à jour du profil utilisateur : nom, prénoms, email, téléphone,
    photo de profil, et changement de mot de passe (avec vérification
    de l'ancien mot de passe).
    """

    current_password = serializers.CharField(write_only=True, required=False)
    new_password = serializers.CharField(write_only=True, required=False, min_length=8)
    photo_profil = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Utilisateur
        fields = [
            "nom", "prenoms", "email", "telephone",
            "photo_profil", "current_password", "new_password",
        ]

    def validate(self, data):
        user = self.instance
        current_password = data.get("current_password")
        new_password = data.get("new_password")

        if new_password:
            if not current_password:
                raise serializers.ValidationError({
                    "current_password": "Vous devez fournir le mot de passe actuel pour changer de mot de passe."
                })

            if not check_password(current_password, user.password):
                raise serializers.ValidationError({
                    "current_password": "Le mot de passe actuel est incorrect."
                })

            try:
                validate_password(new_password, user)
            except DjangoValidationError as e:
                raise serializers.ValidationError({"new_password": list(e.messages)})

            data["password"] = make_password(new_password)

        return data

    def update(self, instance, validated_data):
        validated_data.pop("current_password", None)
        validated_data.pop("new_password", None)

        password = validated_data.pop("password", None)
        if password:
            instance.password = password

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance


# ===================================================================
# 6. RÉINITIALISATION DE MOT DE PASSE PAR CODE (email + code à 6 chiffres)
#    Utilise les champs reset_token / reset_token_expiration du modèle.
# ===================================================================
DUREE_VALIDITE_CODE = timedelta(minutes=15)


class PasswordResetRequestSerializer(serializers.Serializer):
    """Étape 1 : demande de réinitialisation, génère et envoie un code par email."""

    email = serializers.EmailField()

    def validate_email(self, value):
        if not Utilisateur.objects.filter(email__iexact=value, is_active=True).exists():
            raise serializers.ValidationError("Aucun compte actif trouvé avec cet email.")
        return value

    def save(self, **kwargs):
        email = self.validated_data["email"]
        user = Utilisateur.objects.get(email__iexact=email)

        code = f"{random.randint(0, 999999):06d}"
        user.reset_token = code
        user.reset_token_expiration = timezone.now() + DUREE_VALIDITE_CODE
        user.save(update_fields=["reset_token", "reset_token_expiration"])

        send_mail(
            subject="Code de réinitialisation de votre mot de passe",
            message=(
                f"Votre code de réinitialisation est : {code}\n\n"
                f"Ce code expire dans {int(DUREE_VALIDITE_CODE.total_seconds() // 60)} minutes.\n"
                "Si vous n'êtes pas à l'origine de cette demande, ignorez cet email."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
        )
        return user


class PasswordResetCodeVerificationSerializer(serializers.Serializer):
    """Étape 2 (optionnelle) : vérifier le code avant d'afficher le formulaire de nouveau mot de passe."""

    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)

    def validate(self, attrs):
        try:
            user = Utilisateur.objects.get(email__iexact=attrs["email"])
        except Utilisateur.DoesNotExist:
            raise serializers.ValidationError("Code ou email invalide.")

        if user.reset_token != attrs["code"]:
            raise serializers.ValidationError("Code invalide.")

        if not user.reset_token_expiration or user.reset_token_expiration < timezone.now():
            raise serializers.ValidationError("Ce code a expiré, veuillez en demander un nouveau.")

        attrs["user"] = user
        return attrs


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Étape 3 : confirmation avec email + code + nouveau mot de passe."""

    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)
    new_password = serializers.CharField(min_length=8, write_only=True)

    def validate_new_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value

    def validate(self, attrs):
        try:
            user = Utilisateur.objects.get(email__iexact=attrs["email"])
        except Utilisateur.DoesNotExist:
            raise serializers.ValidationError("Code ou email invalide.")

        if user.reset_token != attrs["code"]:
            raise serializers.ValidationError("Code invalide.")

        if not user.reset_token_expiration or user.reset_token_expiration < timezone.now():
            raise serializers.ValidationError("Ce code a expiré, veuillez en demander un nouveau.")

        attrs["user"] = user
        return attrs

    def save(self, **kwargs):
        user = self.validated_data["user"]
        user.set_password(self.validated_data["new_password"])
        # Invalider le code après usage (usage unique)
        user.reset_token = None
        user.reset_token_expiration = None
        user.save()
        return user


# ===================================================================
# 7. INSCRIPTION AGENT (pas de modèle profil dédié, juste Utilisateur)
# ===================================================================
class AgentRegisterSerializer(serializers.Serializer):
    """
    Inscription d'un agent immobilier. Crée un Utilisateur avec role=AGENT.
    Pas de modèle profil dédié (contrairement à Propriétaire/Locataire).
    Le compte est créé inactif (AGENT n'est pas dans ROLES_AUTO_ACTIFS)
    et doit être activé par un administrateur.
    """

    email = serializers.EmailField()
    nom = serializers.CharField(max_length=100)
    prenoms = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=8, validators=[validate_password])
    telephone = serializers.CharField(required=False, allow_blank=True)

    def validate_email(self, value):
        if Utilisateur.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Un compte avec cet email existe déjà.")
        return value

    def save(self, **kwargs):
        data = self.validated_data
        user = Utilisateur.objects.create_user(
            email=data["email"],
            password=data["password"],
            nom=data["nom"],
            prenoms=data["prenoms"],
            role=Utilisateur.Role.AGENT,
            telephone=data.get("telephone", ""),
        )
        return user


# ===================================================================
# 8. LOGIN JWT
# ===================================================================
class UtilisateurTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Login JWT personnalisé : ajoute le rôle et l'email dans le payload du token.
    Note : USERNAME_FIELD = "email" sur le modèle Utilisateur.
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["email"] = user.email
        token["nom_complet"] = user.get_full_name()
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["utilisateur"] = UtilisateurSerializer(self.user, context=self.context).data
        return data