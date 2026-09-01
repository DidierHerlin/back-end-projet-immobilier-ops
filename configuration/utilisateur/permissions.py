from rest_framework.permissions import BasePermission, SAFE_METHODS


class EstAdmin(BasePermission):
    """RG-01 : seul l'administrateur gère les comptes utilisateurs."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == "ADMIN")


class EstProprietaireDuCompte(BasePermission):
    """Un utilisateur ne peut modifier que son propre profil (sauf l'admin)."""
    def has_object_permission(self, request, view, obj):
        if request.user.role == "ADMIN":
            return True
        if request.method in SAFE_METHODS:
            return obj == request.user
        return obj == request.user