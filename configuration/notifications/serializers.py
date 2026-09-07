# immobilier/serializers.py

from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer complet pour la lecture des notifications."""

    type_display = serializers.CharField(source="get_type_display", read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "utilisateur",
            "type",
            "type_display",
            "message",
            "date",
            "lu",
            "email_envoye",
        ]
        read_only_fields = ["id", "utilisateur", "date", "email_envoye"]


class NotificationCreateSerializer(serializers.ModelSerializer):
    """Création de notifications (usage interne / admin)."""

    class Meta:
        model = Notification
        fields = ["utilisateur", "type", "message"]


class MarquerLuSerializer(serializers.Serializer):
    """Permet de marquer une ou plusieurs notifications comme lues."""

    notification_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="Liste d'IDs à marquer comme lues. Si vide, marque TOUTES les notifications de l'utilisateur.",
    )