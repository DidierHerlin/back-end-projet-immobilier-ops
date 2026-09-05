from django.urls import path

from .views import BienViewSet

app_name = "bien"

bien_list = BienViewSet.as_view({
    "get": "list",
    "post": "create",
})

bien_disponible = BienViewSet.as_view({
    "get": "disponibles",
})

bien_detail = BienViewSet.as_view({
    "get": "retrieve",
    "put": "update",
    "patch": "partial_update",
    "delete": "destroy",
})

urlpatterns = [
    # Route dédiée, placée avant "<int:pk>/" pour rester explicite même si
    # "disponible" n'est de toute façon jamais capturé par le converter
    # int:pk.
    path("biens/disponible/", bien_disponible, name="bien-disponible"),
    path("biens/", bien_list, name="bien-list"),
    path("biens/<int:pk>/", bien_detail, name="bien-detail"),
]