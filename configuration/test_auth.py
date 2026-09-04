import django, os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "configuration.settings")
django.setup()

from utilisateur.models import Utilisateur
from django.contrib.auth import authenticate

# Test 1: Verifier que authenticate() fonctionne avec un user existant
email = "testlogin@example.com"
password = "MonMotDePasse1"

# Supprimer si existe deja
Utilisateur.objects.filter(email=email).delete()

# Creer un user de test
user = Utilisateur.objects.create_user(
    email=email,
    password=password,
    nom="Test",
    prenoms="Login",
    role="LOCATAIRE"
)
print(f"Utilisateur cree: {user.email} | active={user.is_active}")
print(f"Password check direct: {user.check_password(password)}")

# Test authenticate()
auth_user = authenticate(email=email, password=password)
print(f"authenticate() result: {auth_user}")

if auth_user is None:
    # Essayer avec username au lieu de email
    auth_user2 = authenticate(username=email, password=password)
    print(f"authenticate(username=...) result: {auth_user2}")
