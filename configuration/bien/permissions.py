"""
Permissions du module Bien.

S'appuie sur le système de rôles déjà présent dans utilisateur.models
(Utilisateur.Role : ADMIN, AGENT, PROPRIETAIRE, LOCATAIRE) et sur la
relation OneToOne réelle user.profil_proprietaire.

Matrice de droits appliquée :

    Rôle            | Create | Read                  | Update      | Delete
    ----------------|--------|-----------------------|-------------|-------
    ADMIN           | Tous   | Tous                  | Tous        | Tous
    AGENT           | Tous   | Tous                  | Tous        | Tous
    PROPRIETAIRE    | Ses    | Ses biens uniquement  | Ses biens   | Non
    LOCATAIRE       | Non    | Biens DISPONIBLE seul.| Non         | Non
"""
from rest_framework.permissions import BasePermission, SAFE_METHODS

from utilisateur.models import Utilisateur

# Rôles ayant un accès de gestion complète (CRUD total) au module Bien.
ROLES_GESTION_COMPLETE = {Utilisateur.Role.ADMIN, Utilisateur.Role.AGENT}

# Rôles ayant un accès de gestion partielle : Create / Read / Update sur
# leurs propres biens uniquement, jamais de Delete.
ROLES_GESTION_PARTIELLE = {Utilisateur.Role.PROPRIETAIRE}

# Rôles en lecture seule, restreints aux biens DISPONIBLE (filtrage
# effectué également dans BienViewSet.get_queryset, cf. défense en
# profondeur ci-dessous).
ROLES_LECTURE_SEULE = {Utilisateur.Role.LOCATAIRE}

# Union de tous les rôles ayant un accès quelconque au module Bien.
ROLES_AUTORISES_BIEN = ROLES_GESTION_COMPLETE | ROLES_GESTION_PARTIELLE | ROLES_LECTURE_SEULE


class PeutGererBien(BasePermission):
    """
    Permission unique pour BienViewSet, appliquée en complément
    d'IsAuthenticated.

    - 401 si non authentifié : garanti en amont par IsAuthenticated dans
      BienViewSet.permission_classes ; has_permission revérifie par
      défense en profondeur (utile si cette permission est réutilisée
      ailleurs sans IsAuthenticated).

    - 403 si authentifié mais :
        * rôle non listé dans ROLES_AUTORISES_BIEN (rôle futur inconnu) ;
        * LOCATAIRE tentant une méthode d'écriture (POST/PUT/PATCH/DELETE) ;
        * PROPRIETAIRE tentant un DELETE.
      Ce contrôle est fait au niveau collection (has_permission), avant
      même d'atteindre get_queryset().

    - Contrôle d'objet (retrieve/update/partial_update/destroy) :
        * ADMIN / AGENT : accès à tous les biens, toutes opérations.
        * PROPRIETAIRE : ses propres biens (toutes actions, jamais en
          DELETE) + lecture seule sur les biens DISPONIBLE d'autrui
          (vitrine publique par ID, ex: GET /api/biens/<id>/).
        * LOCATAIRE : uniquement en lecture (SAFE_METHODS), et uniquement
          si le bien est au statut DISPONIBLE.

      Ce contrôle est une DEUXIÈME barrière : BienViewSet.get_queryset()
      filtre déjà les PROPRIETAIRE sur leurs propres biens et les
      LOCATAIRE sur les biens DISPONIBLE, donc un ID hors périmètre
      renvoie normalement 404 avant même d'appeler has_object_permission.
      Les deux mécanismes sont volontairement redondants (défense en
      profondeur).
    """

    message = "Vous n'avez pas les droits nécessaires sur ce bien."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not (user and user.is_authenticated):
            return False

        role = getattr(user, "role", None)
        if role not in ROLES_AUTORISES_BIEN:
            return False

        # LOCATAIRE : lecture seule, aucune écriture autorisée.
        if role in ROLES_LECTURE_SEULE and request.method not in SAFE_METHODS:
            return False

        # PROPRIETAIRE : jamais de suppression.
        if role in ROLES_GESTION_PARTIELLE and request.method == "DELETE":
            return False

        return True

    def has_object_permission(self, request, view, obj) -> bool:
        user = request.user
        role = getattr(user, "role", None)

        if role in ROLES_GESTION_COMPLETE:
            return True

        if role in ROLES_GESTION_PARTIELLE:
            if request.method == "DELETE":
                return False

            proprietaire = getattr(user, "profil_proprietaire", None)
            est_proprietaire_du_bien = (
                proprietaire is not None and obj.proprietaire_id == proprietaire.pk
            )
            if est_proprietaire_du_bien:
                return True

            # Bien d'un autre propriétaire : consultation seule autorisée
            # si le bien est DISPONIBLE (vitrine publique). Toute écriture
            # (PUT/PATCH) sur le bien d'autrui reste interdite.
            if request.method in SAFE_METHODS:
                return obj.statut == obj.StatutBien.DISPONIBLE
            return False

        if role in ROLES_LECTURE_SEULE:
            if request.method not in SAFE_METHODS:
                return False
            return obj.statut == obj.StatutBien.DISPONIBLE

        return False