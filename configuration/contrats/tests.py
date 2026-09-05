from datetime import date, timedelta
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from utilisateur.models import Utilisateur, Proprietaire, Locataire
from bien.models import Bien
from contrats.models import Contrat


class ContratReglesMetierTestCase(APITestCase):
    def setUp(self):
        # Création des utilisateurs
        self.proprio_user = Utilisateur.objects.create_user(
            email="proprio@test.com", password="pass", role=Utilisateur.Role.PROPRIETAIRE,
            nom="Dupont", prenoms="Jean"
        )
        self.proprietaire = Proprietaire.objects.create(user=self.proprio_user, iban="FR123")
        self.locataire_user = Utilisateur.objects.create_user(
            email="locataire@test.com", password="pass", role=Utilisateur.Role.LOCATAIRE,
            nom="Martin", prenoms="Paul"
        )
        self.locataire = Locataire.objects.create(user=self.locataire_user)

        # Agent pour créer les contrats
        self.agent_user = Utilisateur.objects.create_user(
            email="agent@test.com", password="pass", role=Utilisateur.Role.AGENT,
            nom="Agent", prenoms="Test"
        )

        # Biens disponibles
        self.bien_location = Bien.objects.create(
            proprietaire=self.proprietaire,
            titre="Appart location",
            type="APPARTEMENT",
            mode_transaction="LOCATION",
            adresse="Tana",
            surface=50,
            nombre_pieces=3,
            loyer_mensuel=500000,
            prix=None,
            statut=Bien.StatutBien.DISPONIBLE,
        )
        self.bien_vente = Bien.objects.create(
            proprietaire=self.proprietaire,
            titre="Maison vente",
            type="MAISON",
            mode_transaction="VENTE",
            adresse="Tana",
            surface=100,
            nombre_pieces=4,
            loyer_mensuel=None,
            prix=200000000,
            statut=Bien.StatutBien.DISPONIBLE,
        )

        # Authentification avec l'agent (pour les actions d'écriture)
        self.client.force_authenticate(user=self.agent_user)

    def test_creer_contrat_location_ok(self):
        url = "/api/contrats/"
        data = {
            "bien": self.bien_location.id,
            "locataire": self.locataire.id,
            "type_contrat": "LOCATION",
            "date_debut": date.today().isoformat(),
            "date_fin": (date.today() + timedelta(days=365)).isoformat(),
            "loyer": 500000,
            "depot_garantie": 1000000,
            "prix": None,
            "statut": "ACTIF"
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        contrat = Contrat.objects.get(id=response.data["id"])
        self.assertEqual(contrat.type_contrat, "LOCATION")
        self.assertEqual(contrat.bien.statut, Bien.StatutBien.LOUE)

    def test_creer_contrat_achat_ok(self):
        url = "/api/contrats/"
        data = {
            "bien": self.bien_vente.id,
            "locataire": self.locataire.id,
            "type_contrat": "ACHAT",
            "date_debut": date.today().isoformat(),
            "date_fin": None,
            "loyer": None,
            "depot_garantie": None,
            "prix": 200000000,
            "statut": "ACTIF"
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        contrat = Contrat.objects.get(id=response.data["id"])
        self.assertEqual(contrat.type_contrat, "ACHAT")
        self.assertEqual(contrat.bien.statut, Bien.StatutBien.DISPONIBLE)  # toujours disponible

    def test_creer_contrat_location_sur_bien_vente_echoue(self):
        url = "/api/contrats/"
        data = {
            "bien": self.bien_vente.id,
            "locataire": self.locataire.id,
            "type_contrat": "LOCATION",
            "date_debut": date.today().isoformat(),
            "date_fin": (date.today() + timedelta(days=365)).isoformat(),
            "loyer": 500000,
            "depot_garantie": 1000000,
            "prix": None,
            "statut": "ACTIF"
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_creer_contrat_achat_sur_bien_location_echoue(self):
        url = "/api/contrats/"
        data = {
            "bien": self.bien_location.id,
            "locataire": self.locataire.id,
            "type_contrat": "ACHAT",
            "date_debut": date.today().isoformat(),
            "date_fin": None,
            "loyer": None,
            "depot_garantie": None,
            "prix": 100000000,
            "statut": "ACTIF"
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_resiliation_location_bien_devient_disponible(self):
        # Créer un contrat de location actif
        contrat = Contrat.objects.create(
            bien=self.bien_location,
            locataire=self.locataire,
            type_contrat="LOCATION",
            date_debut=date.today(),
            date_fin=date.today() + timedelta(days=365),
            loyer=500000,
            depot_garantie=1000000,
            statut="ACTIF"
        )
        self.bien_location.refresh_from_db()
        self.assertEqual(self.bien_location.statut, Bien.StatutBien.LOUE)

        # Résilier
        url = f"/api/contrats/{contrat.id}/resilier/"
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        contrat.refresh_from_db()
        self.assertEqual(contrat.statut, Contrat.StatutContrat.RESILIE)
        self.bien_location.refresh_from_db()
        self.assertEqual(self.bien_location.statut, Bien.StatutBien.DISPONIBLE)

    def test_terminaison_location_bien_devient_disponible(self):
        contrat = Contrat.objects.create(
            bien=self.bien_location,
            locataire=self.locataire,
            type_contrat="LOCATION",
            date_debut=date.today(),
            date_fin=date.today() + timedelta(days=365),
            loyer=500000,
            depot_garantie=1000000,
            statut="ACTIF"
        )
        self.bien_location.refresh_from_db()
        self.assertEqual(self.bien_location.statut, Bien.StatutBien.LOUE)

        url = f"/api/contrats/{contrat.id}/terminer/"
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        contrat.refresh_from_db()
        self.assertEqual(contrat.statut, Contrat.StatutContrat.TERMINE)
        self.bien_location.refresh_from_db()
        self.assertEqual(self.bien_location.statut, Bien.StatutBien.DISPONIBLE)

    def test_finalisation_vente_bien_devient_vendu(self):
        contrat = Contrat.objects.create(
            bien=self.bien_vente,
            locataire=self.locataire,
            type_contrat="ACHAT",
            date_debut=date.today(),
            date_fin=None,
            loyer=None,
            depot_garantie=None,
            prix=200000000,
            statut="ACTIF"
        )
        self.bien_vente.refresh_from_db()
        self.assertEqual(self.bien_vente.statut, Bien.StatutBien.DISPONIBLE)

        url = f"/api/contrats/{contrat.id}/finaliser_vente/"
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        contrat.refresh_from_db()
        self.assertEqual(contrat.statut, Contrat.StatutContrat.VENDU)
        self.bien_vente.refresh_from_db()
        self.assertEqual(self.bien_vente.statut, Bien.StatutBien.VENDU)

    def test_creer_contrat_sur_bien_vendu_echoue(self):
        # Finaliser une vente
        contrat = Contrat.objects.create(
            bien=self.bien_vente,
            locataire=self.locataire,
            type_contrat="ACHAT",
            date_debut=date.today(),
            date_fin=None,
            loyer=None,
            depot_garantie=None,
            prix=200000000,
            statut="ACTIF"
        )
        contrat.finaliser_vente()
        self.bien_vente.refresh_from_db()
        self.assertEqual(self.bien_vente.statut, Bien.StatutBien.VENDU)

        # Tenter de créer un nouveau contrat
        url = "/api/contrats/"
        data = {
            "bien": self.bien_vente.id,
            "locataire": self.locataire.id,
            "type_contrat": "LOCATION",
            "date_debut": date.today().isoformat(),
            "date_fin": (date.today() + timedelta(days=365)).isoformat(),
            "loyer": 600000,
            "depot_garantie": 1200000,
            "prix": None,
            "statut": "ACTIF"
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("bien", response.data)

    def test_changement_location_vente_bien_disponible(self):
        bien = Bien.objects.create(
            proprietaire=self.proprietaire,
            titre="Bien mixte",
            type="APPARTEMENT",
            mode_transaction="LOCATION",
            adresse="Tana",
            surface=60,
            nombre_pieces=2,
            loyer_mensuel=400000,
            prix=None,
            statut=Bien.StatutBien.DISPONIBLE,
        )
        url = f"/api/biens/{bien.id}/"
        data = {
            "mode_transaction": "VENTE",
            "prix": 100000000,
            "loyer_mensuel": None,
        }
        response = self.client.patch(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        bien.refresh_from_db()
        self.assertEqual(bien.mode_transaction, "VENTE")
        self.assertIsNotNone(bien.prix)
        self.assertIsNone(bien.loyer_mensuel)
        self.assertEqual(bien.statut, Bien.StatutBien.DISPONIBLE)

    def test_changement_vente_location_bien_disponible(self):
        bien = Bien.objects.create(
            proprietaire=self.proprietaire,
            titre="Bien mixte 2",
            type="MAISON",
            mode_transaction="VENTE",
            adresse="Tana",
            surface=80,
            nombre_pieces=3,
            loyer_mensuel=None,
            prix=150000000,
            statut=Bien.StatutBien.DISPONIBLE,
        )
        url = f"/api/biens/{bien.id}/"
        data = {
            "mode_transaction": "LOCATION",
            "loyer_mensuel": 500000,
            "prix": None,
        }
        response = self.client.patch(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        bien.refresh_from_db()
        self.assertEqual(bien.mode_transaction, "LOCATION")
        self.assertIsNotNone(bien.loyer_mensuel)
        self.assertIsNone(bien.prix)