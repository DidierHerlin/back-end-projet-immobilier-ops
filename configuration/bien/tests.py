from rest_framework import status
from rest_framework.test import APITestCase
from utilisateur.models import Utilisateur, Proprietaire
from bien.models import Bien

class BienReglesMetierTestCase(APITestCase):
    def setUp(self):
        self.user = Utilisateur.objects.create_user(
            email="proprio@test.com", password="pass", role=Utilisateur.Role.PROPRIETAIRE,
            nom="Dupont", prenoms="Jean"
        )
        self.proprietaire = Proprietaire.objects.create(user=self.user, iban="FR123")
        self.client.force_authenticate(user=self.user)

    def test_creation_bien_location_ok(self):
        url = "/api/biens/"
        data = {
            "titre": "Appart à louer",
            "type": "APPARTEMENT",
            "mode_transaction": "LOCATION",
            "adresse": "Tana",
            "surface": 50,
            "nombre_pieces": 3,
            "loyer_mensuel": 500000,
            "prix": None,
            "statut": "DISPONIBLE",
            "photos": []
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_creation_bien_vente_ok(self):
        url = "/api/biens/"
        data = {
            "titre": "Maison à vendre",
            "type": "MAISON",
            "mode_transaction": "VENTE",
            "adresse": "Tana",
            "surface": 120,
            "nombre_pieces": 5,
            "loyer_mensuel": None,
            "prix": 150000000,
            "statut": "DISPONIBLE",
            "photos": []
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_creation_bien_location_avec_prix_echoue(self):
        url = "/api/biens/"
        data = {
            "titre": "Appart location avec prix",
            "type": "APPARTEMENT",
            "mode_transaction": "LOCATION",
            "adresse": "Tana",
            "surface": 50,
            "nombre_pieces": 2,
            "loyer_mensuel": 400000,
            "prix": 80000000,
            "statut": "DISPONIBLE",
            "photos": []
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_creation_bien_vente_sans_prix_echoue(self):
        url = "/api/biens/"
        data = {
            "titre": "Maison vente sans prix",
            "type": "MAISON",
            "mode_transaction": "VENTE",
            "adresse": "Tana",
            "surface": 100,
            "nombre_pieces": 4,
            "loyer_mensuel": None,
            "prix": None,
            "statut": "DISPONIBLE",
            "photos": []
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_creation_terrain_sans_pieces_ok(self):
        url = "/api/biens/"
        data = {
            "titre": "Terrain à vendre",
            "type": "TERRAIN",
            "mode_transaction": "VENTE",
            "adresse": "Tana",
            "surface": 200,
            "nombre_pieces": None,
            "loyer_mensuel": None,
            "prix": 50000000,
            "statut": "DISPONIBLE",
            "photos": []
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_creation_terrain_avec_pieces_echoue(self):
        url = "/api/biens/"
        data = {
            "titre": "Terrain avec pièces",
            "type": "TERRAIN",
            "mode_transaction": "VENTE",
            "adresse": "Tana",
            "surface": 200,
            "nombre_pieces": 3,
            "loyer_mensuel": None,
            "prix": 50000000,
            "statut": "DISPONIBLE",
            "photos": []
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_modification_bien_loue_interdite(self):
        bien = Bien.objects.create(
            proprietaire=self.proprietaire,
            titre="Bien loué",
            type="APPARTEMENT",
            mode_transaction="LOCATION",
            adresse="Tana",
            surface=60,
            nombre_pieces=2,
            loyer_mensuel=600000,
            prix=None,
            statut=Bien.StatutBien.LOUE,
        )
        url = f"/api/biens/{bien.id}/"
        data = {"titre": "Nouveau titre"}
        response = self.client.patch(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_modification_bien_vendu_interdite(self):
        bien = Bien.objects.create(
            proprietaire=self.proprietaire,
            titre="Bien vendu",
            type="MAISON",
            mode_transaction="VENTE",
            adresse="Tana",
            surface=80,
            nombre_pieces=3,
            loyer_mensuel=None,
            prix=100000000,
            statut=Bien.StatutBien.VENDU,
        )
        url = f"/api/biens/{bien.id}/"
        data = {"adresse": "Nouvelle adresse"}
        response = self.client.patch(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_agent_peut_creer_bien_pour_autre_proprietaire(self):
        agent = Utilisateur.objects.create_user(
            email="agent@test.com", password="pass", role=Utilisateur.Role.AGENT,
            nom="Agent", prenoms="Test"
        )
        self.client.force_authenticate(user=agent)
        url = "/api/biens/"
        data = {
            "proprietaire_id": self.proprietaire.id,
            "titre": "Bien par agent",
            "type": "APPARTEMENT",
            "mode_transaction": "LOCATION",
            "adresse": "Tana",
            "surface": 45,
            "nombre_pieces": 2,
            "loyer_mensuel": 300000,
            "prix": None,
            "statut": "DISPONIBLE",
            "photos": []
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        bien = Bien.objects.get(titre="Bien par agent")
        self.assertEqual(bien.proprietaire, self.proprietaire)