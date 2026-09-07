# immobilier/views.py (module Notification)

import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification
from .serializers import (
    MarquerLuSerializer,
    NotificationCreateSerializer,
    NotificationSerializer,
)

logger = logging.getLogger(__name__)


class NotificationListView(APIView):
    """
    GET /api/notifications/
    Filtres optionnels : ?lu=false, ?type=RETARD_PAIEMENT
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = Notification.objects.filter(utilisateur=request.user)

        lu_param = request.query_params.get("lu")
        if lu_param is not None:
            queryset = queryset.filter(lu=lu_param.lower() in ("true", "1"))

        type_param = request.query_params.get("type")
        if type_param:
            queryset = queryset.filter(type=type_param.upper())

        serializer = NotificationSerializer(queryset, many=True)
        return Response({
            "success": True,
            "count": queryset.count(),
            "results": serializer.data,
        }, status=status.HTTP_200_OK)


class NotificationCountView(APIView):
    """GET /api/notifications/non-lues/count/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = Notification.objects.filter(
            utilisateur=request.user, lu=False,
        ).count()
        return Response({"success": True, "count": count}, status=status.HTTP_200_OK)


class NotificationDetailView(APIView):
    """
    GET /api/notifications/<id>/ — détail + marque comme lue automatiquement
    DELETE /api/notifications/<id>/ — suppression
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            notification = Notification.objects.get(pk=pk, utilisateur=request.user)
        except Notification.DoesNotExist:
            return Response({
                "success": False, "error": "Notification non trouvée.",
            }, status=status.HTTP_404_NOT_FOUND)

        if not notification.lu:
            notification.lu = True
            notification.save(update_fields=["lu"])

        serializer = NotificationSerializer(notification)
        return Response({"success": True, "data": serializer.data}, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        try:
            notification = Notification.objects.get(pk=pk, utilisateur=request.user)
        except Notification.DoesNotExist:
            return Response({
                "success": False, "error": "Notification non trouvée.",
            }, status=status.HTTP_404_NOT_FOUND)

        notification.delete()
        return Response({
            "success": True, "message": "Notification supprimée.",
        }, status=status.HTTP_204_NO_CONTENT)


class MarquerLuView(APIView):
    """
    POST /api/notifications/marquer-lu/
    Body : { "notification_ids": [1, 2, 3] } — vide = tout marquer comme lu.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = MarquerLuSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ids = serializer.validated_data.get("notification_ids")
        queryset = Notification.objects.filter(utilisateur=request.user, lu=False)
        if ids:
            queryset = queryset.filter(pk__in=ids)

        count = queryset.update(lu=True)
        return Response({
            "success": True,
            "message": f"{count} notification(s) marquée(s) comme lue(s).",
            "count": count,
        }, status=status.HTTP_200_OK)


class NotificationCreateView(APIView):
    """
    POST /api/notifications/creer/
    Réservé aux administrateurs. Déclenche automatiquement l'envoi d'email
    via le signal post_save défini dans models/notification.py.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role != "ADMIN":
            return Response({
                "success": False,
                "error": "Seul un administrateur peut créer des notifications.",
            }, status=status.HTTP_403_FORBIDDEN)

        serializer = NotificationCreateSerializer(data=request.data)

        if serializer.is_valid():
            notification = serializer.save()
            logger.info(f"Notification créée: {notification}")
            return Response({
                "success": True,
                "message": "Notification créée avec succès.",
                "data": NotificationSerializer(notification).data,
            }, status=status.HTTP_201_CREATED)

        return Response({
            "success": False,
            "error": "Données invalides.",
            "details": serializer.errors,
        }, status=status.HTTP_400_BAD_REQUEST)