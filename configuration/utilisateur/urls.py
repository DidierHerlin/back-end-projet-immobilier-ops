# accounts/urls.py

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    ActiverCompteView,
    AgentRegisterView,
    ChangePasswordView,
    DeleteProfilePhotoView,
    GetProfileView,
    LocataireDetailView,
    LocataireListView,
    LocataireRegisterView,
    LoginView,
    LogoutView,
    ProprietaireDetailView,
    ProprietaireListView,
    ProprietaireRegisterView,
    RequestPasswordResetView,
    ResetPasswordView,
    UpdateProfilePhotoView,
    UpdateUserProfileView,
    VerifyResetCodeView,
)

urlpatterns = [
    # -----------------------------------------------------------------
    # Authentification
    # -----------------------------------------------------------------
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    # -----------------------------------------------------------------
    # Inscription
    # -----------------------------------------------------------------
    path("locataires/register/", LocataireRegisterView.as_view(), name="locataire-register"),
    path("proprietaires/register/", ProprietaireRegisterView.as_view(), name="proprietaire-register"),
    path("agents/register/", AgentRegisterView.as_view(), name="agent-register"),

    # -----------------------------------------------------------------
    # Locataires (agent/admin : liste + détail par id ; locataire : /me/)
    # -----------------------------------------------------------------
    path("locataires/", LocataireListView.as_view(), name="locataire-list"),
    path("locataires/me/", LocataireDetailView.as_view(), name="locataire-me"),
    path("locataires/<int:pk>/", LocataireDetailView.as_view(), name="locataire-detail"),

    # -----------------------------------------------------------------
    # Propriétaires (agent/admin : liste + détail par id ; propriétaire : /me/)
    # -----------------------------------------------------------------
    path("proprietaires/", ProprietaireListView.as_view(), name="proprietaire-list"),
    path("proprietaires/me/", ProprietaireDetailView.as_view(), name="proprietaire-me"),
    path("proprietaires/<int:pk>/", ProprietaireDetailView.as_view(), name="proprietaire-detail"),

    # -----------------------------------------------------------------
    # Activation de compte (agent/admin)
    # -----------------------------------------------------------------
    path("utilisateurs/<int:pk>/activer/", ActiverCompteView.as_view(), name="activer-compte"),

    # -----------------------------------------------------------------
    # Profil personnel (tous rôles)
    # -----------------------------------------------------------------
    path("profil/", GetProfileView.as_view(), name="profil-me"),
    path("profil/modifier/", UpdateUserProfileView.as_view(), name="profil-modifier"),
    path("profil/photo/", UpdateProfilePhotoView.as_view(), name="profil-photo-maj"),
    path("profil/photo/supprimer/", DeleteProfilePhotoView.as_view(), name="profil-photo-supprimer"),
    path("profil/changer-mot-de-passe/", ChangePasswordView.as_view(), name="changer-mot-de-passe"),

    # -----------------------------------------------------------------
    # Mot de passe oublié (3 étapes, public)
    # -----------------------------------------------------------------
    path("mot-de-passe/demande/", RequestPasswordResetView.as_view(), name="mdp-demande"),
    path("mot-de-passe/verifier-code/", VerifyResetCodeView.as_view(), name="mdp-verifier-code"),
    path("mot-de-passe/reinitialiser/", ResetPasswordView.as_view(), name="mdp-reinitialiser"),
]