from django.db import migrations

def mettre_a_jour_terrains(apps, schema_editor):
    Bien = apps.get_model('bien', 'Bien')
    # Mettre nombre_pieces à NULL pour tous les terrains
    Bien.objects.filter(type='TERRAIN').update(nombre_pieces=None)

class Migration(migrations.Migration):
    dependencies = [
        ('bien', '0002_remove_bien_bien_nombre_pieces_positive_and_more'),  # ← le nom exact de votre migration précédente
    ]
    operations = [
        migrations.RunPython(mettre_a_jour_terrains, reverse_code=migrations.RunPython.noop),
    ]