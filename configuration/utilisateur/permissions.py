# api/permissions.py
"""
Classes de permission DRF centralisées.

Remplace les contrôles `if request.user.role not in ROLES_GESTIONNAIRES: ...`
dispersés dans views.py par des permission_classes réutilisables et testables.
"""

from rest_framework.permissions import BasePermission, SAFE_METHODS


class EstAdmin(BasePermission):
    """RG-01 : seul l'administrateur gère certaines actions sensibles
    (activation de compte, suppression définitive, etc.)."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == "ADMIN"
        )


class EstGestionnaire(BasePermission):
    """Agent immobilier ou Administrateur — équivalent de ROLES_GESTIONNAIRES
    utilisé pour la gestion quotidienne des fiches Propriétaire/Locataire."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in ("AGENT", "ADMIN")
        )


class EstProprietaireDuCompte(BasePermission):
    """
    Un utilisateur ne peut modifier que son propre compte (sauf l'admin).

    À utiliser uniquement sur des vues dont l'objet consulté (`obj`)
    EST directement une instance de Utilisateur — par exemple GetProfileView.
    """

    def has_object_permission(self, request, view, obj):
        if request.user.role == "ADMIN":
            return True
        return obj == request.user


class EstProprietaireDuProfil(BasePermission):
    """
    CORRECTION : variante de EstProprietaireDuCompte pour les objets
    Proprietaire / Locataire (qui NE SONT PAS directement des Utilisateur,
    mais qui possèdent un attribut `.user`).

    À utiliser sur ProprietaireDetailView / LocataireDetailView, où
    `obj == request.user` échouerait toujours (obj est un Proprietaire
    ou un Locataire, jamais égal à l'instance Utilisateur connectée).
    """

    def has_object_permission(self, request, view, obj):
        if request.user.role == "ADMIN":
            return True
        if request.method in SAFE_METHODS and request.user.role in ("AGENT", "ADMIN"):
            return True
        return obj.user == request.user