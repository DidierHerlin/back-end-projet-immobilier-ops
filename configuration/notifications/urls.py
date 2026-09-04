# immobilier/urls.py (extrait à fusionner avec tes autres routes)

from django.urls import path

from .views import (
    NotificationListView,
    NotificationCountView,
    NotificationDetailView,
    MarquerLuView,
    NotificationCreateView,
)

urlpatterns = [
    # ... tes autres routes (biens, contrats, paiements, etc.) ...

    path("notifications/", NotificationListView.as_view(), name="notification-list"),
    path("notifications/non-lues/count/", NotificationCountView.as_view(), name="notification-count"),
    path("notifications/creer/", NotificationCreateView.as_view(), name="notification-create"),
    path("notifications/marquer-lu/", MarquerLuView.as_view(), name="notification-marquer-lu"),
    path("notifications/<int:pk>/", NotificationDetailView.as_view(), name="notification-detail"),
]