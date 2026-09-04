from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "utilisateur", "type", "message_court", "date", "lu")
    list_filter = ("type", "lu", "date")
    search_fields = ("utilisateur__email", "utilisateur__nom", "message")
    list_editable = ("lu",)
    ordering = ("-date",)

    def message_court(self, obj):
        """Affiche les 80 premiers caractères du message."""
        return obj.message[:80] + "…" if len(obj.message) > 80 else obj.message
    message_court.short_description = "Message"
