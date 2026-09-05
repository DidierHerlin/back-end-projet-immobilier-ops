from rest_framework import permissions
from utilisateur.models import Utilisateur

class ContratPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.role in (Utilisateur.Role.ADMIN, Utilisateur.Role.AGENT)

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.role in (Utilisateur.Role.ADMIN, Utilisateur.Role.AGENT)