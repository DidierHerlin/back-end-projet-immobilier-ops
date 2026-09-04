import django, os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "configuration.settings")
django.setup()

from utilisateur.models import Utilisateur

for u in Utilisateur.objects.all():
    print(f"Email: {u.email} | Role: {u.role} | Active: {u.is_active} | Has password: {u.has_usable_password()}")

# Test du login pour le premier utilisateur
email = "didierherlin18@example.com"
try:
    user = Utilisateur.objects.get(email=email)
    print(f"\nTest mot de passe pour {email}:")
    print(f"  Password hash: {user.password[:30]}...")
    print(f"  Algorithm: {user.password.split('$')[0] if '$' in user.password else 'unknown'}")
except Utilisateur.DoesNotExist:
    print(f"Utilisateur {email} non trouve")
