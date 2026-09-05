from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone
from .models import Contrat
from .serializers import ContratSerializer
from .permissions import ContratPermission
from bien.models import Bien


class ContratViewSet(viewsets.ModelViewSet):
    queryset = Contrat.objects.select_related("bien", "locataire")
    serializer_class = ContratSerializer
    permission_classes = [permissions.IsAuthenticated, ContratPermission]
    filterset_fields = ["statut", "type_contrat", "bien", "locataire"]
    ordering_fields = ["date_creation", "date_debut", "date_fin", "loyer", "prix"]
    ordering = ["-date_creation"]

    def get_initial(self):
        """
        Définit des valeurs par défaut pour la création d'un contrat.
        """
        initial = super().get_initial()
        request = self.request

        type_contrat = request.query_params.get('type_contrat')
        bien_id = request.query_params.get('bien_id')

        # Si un bien est spécifié, récupérer ses informations
        if bien_id:
            try:
                bien = Bien.objects.get(id=bien_id, statut=Bien.StatutBien.DISPONIBLE)

                if type_contrat == Contrat.TypeContrat.LOCATION:
                    initial['loyer'] = bien.loyer_mensuel
                    if bien.loyer_mensuel:
                        initial['depot_garantie'] = bien.loyer_mensuel * 2
                elif type_contrat == Contrat.TypeContrat.ACHAT:
                    initial['prix'] = bien.prix
                    initial['date_debut'] = timezone.now().date().isoformat()
                    initial['date_fin'] = None
            except Bien.DoesNotExist:
                pass

        # Si type_contrat est ACHAT sans bien spécifié, date_debut = aujourd'hui
        if type_contrat == Contrat.TypeContrat.ACHAT and not bien_id:
            initial['date_debut'] = timezone.now().date().isoformat()
            initial['date_fin'] = None

        return initial

    @action(detail=False, methods=["get"])
    def bien_info(self, request):
        bien_id = request.query_params.get("bien_id")
        if not bien_id:
            return Response({"error": "bien_id est requis."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            bien = Bien.objects.get(id=bien_id, statut=Bien.StatutBien.DISPONIBLE)
        except Bien.DoesNotExist:
            return Response({"error": "Bien non trouvé ou indisponible."}, status=status.HTTP_404_NOT_FOUND)
        data = {
            "loyer_mensuel": bien.loyer_mensuel,
            "prix": bien.prix,
            "mode_transaction": bien.mode_transaction,
            "type": bien.type,
            "surface": bien.surface,
            "adresse": bien.adresse,
            "titre": bien.titre,
        }
        return Response(data)

    @action(detail=True, methods=["post"])
    def resilier(self, request, pk=None):
        contrat = self.get_object()
        if contrat.type_contrat != Contrat.TypeContrat.LOCATION:
            return Response({"error": "Seuls les contrats de location peuvent être résiliés."},
                            status=status.HTTP_400_BAD_REQUEST)
        if contrat.statut != Contrat.StatutContrat.ACTIF:
            return Response({"error": "Seul un contrat actif peut être résilié."},
                            status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            contrat.resilier()
        return Response(ContratSerializer(contrat).data)

    @action(detail=True, methods=["post"])
    def terminer(self, request, pk=None):
        contrat = self.get_object()
        if contrat.type_contrat != Contrat.TypeContrat.LOCATION:
            return Response({"error": "Seuls les contrats de location peuvent être terminés."},
                            status=status.HTTP_400_BAD_REQUEST)
        if contrat.statut != Contrat.StatutContrat.ACTIF:
            return Response({"error": "Seul un contrat actif peut être terminé."},
                            status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            contrat.terminer()
        return Response(ContratSerializer(contrat).data)

    @action(detail=True, methods=["post"])
    def finaliser_vente(self, request, pk=None):
        contrat = self.get_object()
        if contrat.type_contrat != Contrat.TypeContrat.ACHAT:
            return Response({"error": "Seuls les contrats d'achat peuvent être finalisés."},
                            status=status.HTTP_400_BAD_REQUEST)
        if contrat.statut != Contrat.StatutContrat.ACTIF:
            return Response({"error": "Seul un contrat actif peut être finalisé."},
                            status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            contrat.finaliser_vente()
        return Response(ContratSerializer(contrat).data)