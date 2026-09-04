# api/views.py

import logging

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

# CORRECTION : imports JWT — remplacent authenticate / auth_login / auth_logout
# / SessionAuthentication, qui géraient une authentification par SESSION,
# incompatible avec l'exigence "authentification JWT" du cahier des charges.
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from .models import Locataire, Proprietaire, Utilisateur
from .serializers import (
    AgentRegisterSerializer,
    LocataireSerializer,
    PasswordResetCodeVerificationSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ProprietaireSerializer,
    UpdateProfilePhotoSerializer,
    UtilisateurSerializer,
    UtilisateurTokenObtainPairSerializer,  # CORRECTION : serializer JWT désormais utilisé
    UtilisateurUpdateSerializer,
)

logger = logging.getLogger(__name__)

# Rôles habilités à gérer les fiches Propriétaire/Locataire (équivalent de
# "scolarite" dans l'ancien projet, qui gérait les fiches Etudiant).
ROLES_GESTIONNAIRES = (Utilisateur.Role.AGENT, Utilisateur.Role.ADMIN)


# ===================================================================
# AUTHENTIFICATION JWT (CORRIGÉ)
# ===================================================================

@method_decorator(csrf_exempt, name="dispatch")
class LoginView(TokenObtainPairView):
    """
    Connexion utilisateur — retourne un couple (access, refresh) de tokens JWT
    ainsi que le profil de l'utilisateur connecté.

    Utilise UtilisateurTokenObtainPairSerializer (déjà défini dans
    serializers.py), qui enrichit le payload du token avec le rôle et
    ajoute le profil utilisateur dans la réponse.

    RG-04 : un compte désactivé (is_active=False) ne peut plus se connecter —
    ce comportement est garanti nativement par TokenObtainPairSerializer,
    qui vérifie `user.is_active` avant d'émettre un token.
    """
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = UtilisateurTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        try:
            serializer.is_valid(raise_exception=True)
        except Exception:
            return Response({
                "success": False,
                "error": "Email ou mot de passe incorrect",
            }, status=status.HTTP_401_UNAUTHORIZED)

        data = serializer.validated_data
        return Response({
            "success": True,
            "message": "Connexion réussie",
            "access": str(data["access"]),
            "refresh": str(data["refresh"]),
            "user": data["utilisateur"],
        }, status=status.HTTP_200_OK)


class LogoutView(APIView):
    """
    Déconnexion utilisateur — blackliste le refresh token transmis
    (rest_framework_simplejwt.token_blacklist doit être dans INSTALLED_APPS).

    Le client doit envoyer son refresh token dans le corps de la requête :
        POST /api/auth/logout/
        { "refresh": "<refresh_token>" }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")

        if not refresh_token:
            return Response({
                "success": False,
                "error": "Le refresh token est requis pour la déconnexion",
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            return Response({
                "success": False,
                "error": "Token invalide ou déjà expiré",
            }, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "success": True,
            "message": "Déconnexion réussie",
        }, status=status.HTTP_200_OK)


# ===================================================================
# INSCRIPTION
# ===================================================================

class LocataireRegisterView(APIView):
    """
    Inscription des locataires.
    RG : un locataire est activé automatiquement (ROLES_AUTO_ACTIFS du manager).
    """
    permission_classes = [AllowAny]
    authentication_classes = []
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def post(self, request):
        logger.info(f"Tentative d'inscription locataire: {request.data.get('email')}")

        serializer = LocataireSerializer(data=request.data, context={"request": request})

        if serializer.is_valid():
            try:
                with transaction.atomic():
                    locataire = serializer.save()

                logger.info(f"Locataire créé avec succès: {locataire.user.email}")

                return Response({
                    "success": True,
                    "message": "Inscription réussie",
                    "data": LocataireSerializer(locataire, context={"request": request}).data,
                }, status=status.HTTP_201_CREATED)

            except Exception as e:
                logger.error(f"Erreur lors de la création du locataire: {str(e)}")
                return Response({
                    "success": False,
                    "error": "Erreur lors de la création du compte",
                    "details": str(e),
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        logger.warning(f"Validation échouée: {serializer.errors}")

        return Response({
            "success": False,
            "error": "Données invalides",
            "details": serializer.errors,
        }, status=status.HTTP_400_BAD_REQUEST)


class ProprietaireRegisterView(APIView):
    """
    Inscription des propriétaires.
    RG : un compte PROPRIETAIRE est créé inactif et doit être validé par un
    administrateur ou un agent avant de pouvoir se connecter (voir manager).
    """
    permission_classes = [AllowAny]
    authentication_classes = []
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def post(self, request):
        logger.info(f"Tentative d'inscription propriétaire: {request.data.get('email')}")

        serializer = ProprietaireSerializer(data=request.data, context={"request": request})

        if serializer.is_valid():
            try:
                with transaction.atomic():
                    proprietaire = serializer.save()

                logger.info(f"Propriétaire créé (en attente de validation): {proprietaire.user.email}")

                return Response({
                    "success": True,
                    "message": "Inscription enregistrée. Votre compte sera activé après validation par un agent.",
                    "data": ProprietaireSerializer(proprietaire, context={"request": request}).data,
                }, status=status.HTTP_201_CREATED)

            except Exception as e:
                logger.error(f"Erreur lors de la création du propriétaire: {str(e)}")
                return Response({
                    "success": False,
                    "error": "Erreur lors de la création du compte",
                    "details": str(e),
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        logger.warning(f"Validation propriétaire échouée: {serializer.errors}")

        return Response({
            "success": False,
            "error": "Données invalides",
            "details": serializer.errors,
        }, status=status.HTTP_400_BAD_REQUEST)


class AgentRegisterView(APIView):
    """
    Inscription des agents immobiliers.
    RG : un compte AGENT est créé inactif et doit être validé par un
    administrateur avant de pouvoir se connecter.
    """
    permission_classes = [AllowAny]
    authentication_classes = []
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def post(self, request):
        logger.info(f"Tentative d'inscription agent: {request.data.get('email')}")

        serializer = AgentRegisterSerializer(data=request.data, context={"request": request})

        if serializer.is_valid():
            try:
                with transaction.atomic():
                    user = serializer.save()

                logger.info(f"Agent créé (en attente de validation): {user.email}")

                return Response({
                    "success": True,
                    "message": "Inscription enregistrée. Votre compte sera activé après validation par un administrateur.",
                    "data": UtilisateurSerializer(user, context={"request": request}).data,
                }, status=status.HTTP_201_CREATED)

            except Exception as e:
                logger.error(f"Erreur lors de la création de l'agent: {str(e)}")
                return Response({
                    "success": False,
                    "error": "Erreur lors de la création du compte",
                    "details": str(e),
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        logger.warning(f"Validation agent échouée: {serializer.errors}")

        return Response({
            "success": False,
            "error": "Données invalides",
            "details": serializer.errors,
        }, status=status.HTTP_400_BAD_REQUEST)


# ===================================================================
# GESTION PROFIL LOCATAIRE
# ===================================================================

class LocataireDetailView(APIView):
    """Détails et modification de la fiche locataire"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None):
        """
        GET /api/locataires/me/     → Profil du locataire connecté
        GET /api/locataires/<id>/   → Profil spécifique (agent/admin uniquement)
        """
        if pk:
            if request.user.role not in ROLES_GESTIONNAIRES:
                return Response({
                    "success": False,
                    "error": "Accès refusé. Réservé à l'agence.",
                }, status=status.HTTP_403_FORBIDDEN)

            locataire = get_object_or_404(Locataire, pk=pk)
        else:
            try:
                locataire = Locataire.objects.get(user=request.user)
            except Locataire.DoesNotExist:
                if request.user.role in ROLES_GESTIONNAIRES:
                    return Response({
                        "success": True,
                        "message": "Vous êtes connecté en tant qu'agent/administrateur",
                        "user": UtilisateurSerializer(request.user, context={"request": request}).data,
                    }, status=status.HTTP_200_OK)

                return Response({
                    "success": False,
                    "error": "Fiche locataire non trouvée",
                }, status=status.HTTP_404_NOT_FOUND)

        serializer = LocataireSerializer(locataire, context={"request": request})
        return Response({
            "success": True,
            "data": serializer.data,
        }, status=status.HTTP_200_OK)

    def put(self, request, pk=None):
        """Mise à jour de la fiche (le locataire modifie son propre profil)."""
        try:
            locataire = Locataire.objects.get(user=request.user)
        except Locataire.DoesNotExist:
            return Response({
                "success": False,
                "error": "Vous devez être locataire pour modifier ce profil",
            }, status=status.HTTP_403_FORBIDDEN)

        if pk and str(locataire.pk) != str(pk):
            return Response({
                "success": False,
                "error": "Vous ne pouvez modifier que votre propre profil",
            }, status=status.HTTP_403_FORBIDDEN)

        serializer = LocataireSerializer(
            locataire, data=request.data, partial=True, context={"request": request}
        )

        if serializer.is_valid():
            try:
                with transaction.atomic():
                    locataire_updated = serializer.save()

                return Response({
                    "success": True,
                    "message": "Profil mis à jour avec succès",
                    "data": LocataireSerializer(locataire_updated, context={"request": request}).data,
                }, status=status.HTTP_200_OK)

            except Exception as e:
                logger.error(f"Erreur mise à jour locataire: {str(e)}")
                return Response({
                    "success": False,
                    "error": "Erreur lors de la mise à jour",
                    "details": str(e),
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            "success": False,
            "error": "Données invalides",
            "details": serializer.errors,
        }, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk=None):
        """Suppression (agent/admin uniquement)."""
        if request.user.role not in ROLES_GESTIONNAIRES:
            return Response({
                "success": False,
                "error": "Seule l'agence peut supprimer un locataire",
            }, status=status.HTTP_403_FORBIDDEN)

        if not pk:
            return Response({
                "success": False,
                "error": "ID du locataire requis",
            }, status=status.HTTP_400_BAD_REQUEST)

        locataire = get_object_or_404(Locataire, pk=pk)
        user = locataire.user

        try:
            with transaction.atomic():
                locataire.delete()
                # RG-04 : désactivation logique plutôt que suppression physique
                user.is_active = False
                user.save(update_fields=["is_active"])

            logger.info(f"Locataire désactivé: {user.email}")

            return Response({
                "success": True,
                "message": "Locataire désactivé avec succès",
            }, status=status.HTTP_204_NO_CONTENT)

        except Exception as e:
            logger.error(f"Erreur suppression locataire: {str(e)}")
            return Response({
                "success": False,
                "error": "Erreur lors de la suppression",
                "details": str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LocataireListView(APIView):
    """Liste de tous les locataires (agent/admin uniquement)"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in ROLES_GESTIONNAIRES:
            return Response({
                "success": False,
                "error": "Accès refusé. Réservé à l'agence.",
            }, status=status.HTTP_403_FORBIDDEN)

        locataires = Locataire.objects.select_related("user").all()
        serializer = LocataireSerializer(locataires, many=True, context={"request": request})

        return Response({
            "success": True,
            "count": locataires.count(),
            "results": serializer.data,
        }, status=status.HTTP_200_OK)


# ===================================================================
# GESTION PROFIL PROPRIÉTAIRE
# ===================================================================

class ProprietaireDetailView(APIView):
    """Détails et modification de la fiche propriétaire"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None):
        """
        GET /api/proprietaires/me/     → Profil du propriétaire connecté
        GET /api/proprietaires/<id>/   → Profil spécifique (agent/admin uniquement)
        """
        if pk:
            if request.user.role not in ROLES_GESTIONNAIRES:
                return Response({
                    "success": False,
                    "error": "Accès refusé. Réservé à l'agence.",
                }, status=status.HTTP_403_FORBIDDEN)

            proprietaire = get_object_or_404(Proprietaire, pk=pk)
        else:
            try:
                proprietaire = Proprietaire.objects.get(user=request.user)
            except Proprietaire.DoesNotExist:
                if request.user.role in ROLES_GESTIONNAIRES:
                    return Response({
                        "success": True,
                        "message": "Vous êtes connecté en tant qu'agent/administrateur",
                        "user": UtilisateurSerializer(request.user, context={"request": request}).data,
                    }, status=status.HTTP_200_OK)

                return Response({
                    "success": False,
                    "error": "Fiche propriétaire non trouvée",
                }, status=status.HTTP_404_NOT_FOUND)

        # RG-09 : un propriétaire ne peut consulter que ses propres données
        if pk and request.user.role == Utilisateur.Role.PROPRIETAIRE:
            return Response({
                "success": False,
                "error": "Accès refusé.",
            }, status=status.HTTP_403_FORBIDDEN)

        serializer = ProprietaireSerializer(proprietaire, context={"request": request})
        return Response({
            "success": True,
            "data": serializer.data,
        }, status=status.HTTP_200_OK)

    def put(self, request, pk=None):
        """Mise à jour de la fiche (le propriétaire modifie son propre profil)."""
        try:
            proprietaire = Proprietaire.objects.get(user=request.user)
        except Proprietaire.DoesNotExist:
            return Response({
                "success": False,
                "error": "Vous devez être propriétaire pour modifier ce profil",
            }, status=status.HTTP_403_FORBIDDEN)

        if pk and str(proprietaire.pk) != str(pk):
            return Response({
                "success": False,
                "error": "Vous ne pouvez modifier que votre propre profil",
            }, status=status.HTTP_403_FORBIDDEN)

        serializer = ProprietaireSerializer(
            proprietaire, data=request.data, partial=True, context={"request": request}
        )

        if serializer.is_valid():
            try:
                with transaction.atomic():
                    proprietaire_updated = serializer.save()

                return Response({
                    "success": True,
                    "message": "Profil mis à jour avec succès",
                    "data": ProprietaireSerializer(proprietaire_updated, context={"request": request}).data,
                }, status=status.HTTP_200_OK)

            except Exception as e:
                logger.error(f"Erreur mise à jour propriétaire: {str(e)}")
                return Response({
                    "success": False,
                    "error": "Erreur lors de la mise à jour",
                    "details": str(e),
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            "success": False,
            "error": "Données invalides",
            "details": serializer.errors,
        }, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk=None):
        """Suppression (agent/admin uniquement)."""
        if request.user.role not in ROLES_GESTIONNAIRES:
            return Response({
                "success": False,
                "error": "Seule l'agence peut supprimer un propriétaire",
            }, status=status.HTTP_403_FORBIDDEN)

        if not pk:
            return Response({
                "success": False,
                "error": "ID du propriétaire requis",
            }, status=status.HTTP_400_BAD_REQUEST)

        proprietaire = get_object_or_404(Proprietaire, pk=pk)
        user = proprietaire.user

        try:
            with transaction.atomic():
                proprietaire.delete()
                user.is_active = False
                user.save(update_fields=["is_active"])

            logger.info(f"Propriétaire désactivé: {user.email}")

            return Response({
                "success": True,
                "message": "Propriétaire désactivé avec succès",
            }, status=status.HTTP_204_NO_CONTENT)

        except Exception as e:
            logger.error(f"Erreur suppression propriétaire: {str(e)}")
            return Response({
                "success": False,
                "error": "Erreur lors de la suppression",
                "details": str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProprietaireListView(APIView):
    """Liste de tous les propriétaires (agent/admin uniquement)"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in ROLES_GESTIONNAIRES:
            return Response({
                "success": False,
                "error": "Accès refusé. Réservé à l'agence.",
            }, status=status.HTTP_403_FORBIDDEN)

        proprietaires = Proprietaire.objects.select_related("user").all()
        serializer = ProprietaireSerializer(proprietaires, many=True, context={"request": request})

        return Response({
            "success": True,
            "count": proprietaires.count(),
            "results": serializer.data,
        }, status=status.HTTP_200_OK)


class ActiverCompteView(APIView):
    """
    Activation manuelle d'un compte PROPRIETAIRE ou AGENT créé inactif
    (agent/admin uniquement).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk=None):
        if request.user.role not in ROLES_GESTIONNAIRES:
            return Response({
                "success": False,
                "error": "Accès refusé. Réservé à l'agence.",
            }, status=status.HTTP_403_FORBIDDEN)

        utilisateur = get_object_or_404(Utilisateur, pk=pk)

        if utilisateur.is_active:
            return Response({
                "success": False,
                "error": "Ce compte est déjà actif.",
            }, status=status.HTTP_400_BAD_REQUEST)

        utilisateur.is_active = True
        utilisateur.save(update_fields=["is_active"])

        logger.info(f"Compte activé: {utilisateur.email}")

        return Response({
            "success": True,
            "message": "Compte activé avec succès.",
        }, status=status.HTTP_200_OK)


# ===================================================================
# GESTION PROFIL UTILISATEUR (générique, tous rôles)
# ===================================================================

class GetProfileView(APIView):
    """Récupérer le profil de l'utilisateur connecté"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UtilisateurSerializer(request.user, context={"request": request})
        return Response({
            "success": True,
            "user": serializer.data,
        }, status=status.HTTP_200_OK)


class UpdateUserProfileView(APIView):
    """Mise à jour complète du profil utilisateur"""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def put(self, request):
        serializer = UtilisateurUpdateSerializer(
            request.user, data=request.data, partial=True, context={"request": request}
        )

        if serializer.is_valid():
            try:
                user = serializer.save()

                return Response({
                    "success": True,
                    "message": "Profil mis à jour avec succès",
                    "user": UtilisateurSerializer(user, context={"request": request}).data,
                }, status=status.HTTP_200_OK)

            except Exception as e:
                logger.error(f"Erreur mise à jour profil: {str(e)}")
                return Response({
                    "success": False,
                    "error": "Erreur lors de la mise à jour",
                    "details": str(e),
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            "success": False,
            "error": "Données invalides",
            "details": serializer.errors,
        }, status=status.HTTP_400_BAD_REQUEST)


class UpdateProfilePhotoView(APIView):
    """Mise à jour de la photo de profil uniquement"""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = UpdateProfilePhotoSerializer(data=request.data)

        if serializer.is_valid():
            try:
                user = request.user

                if user.photo_profil:
                    user.photo_profil.delete(save=False)

                user.photo_profil = serializer.validated_data["photo_profil"]
                user.save()

                return Response({
                    "success": True,
                    "message": "Photo de profil mise à jour avec succès",
                    "user": UtilisateurSerializer(user, context={"request": request}).data,
                }, status=status.HTTP_200_OK)

            except Exception as e:
                logger.error(f"Erreur mise à jour photo: {str(e)}")
                return Response({
                    "success": False,
                    "error": "Erreur lors de la mise à jour de la photo",
                    "details": str(e),
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            "success": False,
            "error": "Données invalides",
            "details": serializer.errors,
        }, status=status.HTTP_400_BAD_REQUEST)


class DeleteProfilePhotoView(APIView):
    """Suppression de la photo de profil"""
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        user = request.user

        if not user.photo_profil:
            return Response({
                "success": False,
                "error": "Aucune photo de profil à supprimer",
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            user.photo_profil.delete(save=True)

            return Response({
                "success": True,
                "message": "Photo de profil supprimée avec succès",
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Erreur suppression photo: {str(e)}")
            return Response({
                "success": False,
                "error": "Erreur lors de la suppression de la photo",
                "details": str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ChangePasswordView(APIView):
    """Changement de mot de passe (nécessite l'ancien mot de passe)"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        current_password = request.data.get("current_password")
        new_password = request.data.get("new_password")

        if not current_password or not new_password:
            return Response({
                "success": False,
                "error": "Mot de passe actuel et nouveau mot de passe requis",
            }, status=status.HTTP_400_BAD_REQUEST)

        serializer = UtilisateurUpdateSerializer(
            request.user,
            data={"current_password": current_password, "new_password": new_password},
            partial=True,
            context={"request": request},
        )

        if serializer.is_valid():
            try:
                serializer.save()

                logger.info(f"Mot de passe changé pour: {request.user.email}")

                return Response({
                    "success": True,
                    "message": "Mot de passe changé avec succès",
                }, status=status.HTTP_200_OK)

            except Exception as e:
                logger.error(f"Erreur changement mot de passe: {str(e)}")
                return Response({
                    "success": False,
                    "error": "Erreur lors du changement de mot de passe",
                    "details": str(e),
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            "success": False,
            "error": "Validation échouée",
            "details": serializer.errors,
        }, status=status.HTTP_400_BAD_REQUEST)


# ===================================================================
# RÉINITIALISATION MOT DE PASSE (3 étapes, par code — cf. serializers.py)
# ===================================================================

@method_decorator(csrf_exempt, name="dispatch")
class RequestPasswordResetView(APIView):
    """Étape 1 : Demande de réinitialisation - Envoie un code par email"""
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)

        if not serializer.is_valid():
            return Response({
                "success": False,
                "error": "Email invalide",
                "details": serializer.errors,
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Le serializer génère le code, le sauvegarde (reset_token /
            # reset_token_expiration) et envoie l'email.
            serializer.save()

            logger.info(f"Code de réinitialisation envoyé à: {serializer.validated_data['email']}")

            return Response({
                "success": True,
                "message": "Code envoyé par email avec succès",
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Erreur envoi email: {str(e)}")
            return Response({
                "success": False,
                "error": "Erreur lors de l'envoi de l'email",
                "details": str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@method_decorator(csrf_exempt, name="dispatch")
class VerifyResetCodeView(APIView):
    """Étape 2 : Vérification du code"""
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = PasswordResetCodeVerificationSerializer(data=request.data)

        if not serializer.is_valid():
            return Response({
                "success": False,
                "error": "Code ou email invalide",
                "details": serializer.errors,
            }, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "success": True,
            "message": "Code valide",
        }, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class ResetPasswordView(APIView):
    """Étape 3 : Réinitialisation finale du mot de passe"""
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)

        if not serializer.is_valid():
            return Response({
                "success": False,
                "error": "Données invalides",
                "details": serializer.errors,
            }, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()

        logger.info(f"Mot de passe réinitialisé pour: {serializer.validated_data['email']}")

        return Response({
            "success": True,
            "message": "Mot de passe réinitialisé avec succès",
        }, status=status.HTTP_200_OK)