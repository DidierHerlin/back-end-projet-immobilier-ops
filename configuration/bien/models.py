from django.db import models
from django.core.exceptions import ValidationError
from utilisateur.models import Proprietaire
from .validators import validate_loyer_mensuel, validate_nombre_pieces, validate_photos, validate_surface, PositiveValueValidator


class Bien(models.Model):
    class TypeBien(models.TextChoices):
        APPARTEMENT = "APPARTEMENT", "Appartement"
        MAISON = "MAISON", "Maison"
        LOCAL_COMMERCIAL = "LOCAL_COMMERCIAL", "Local commercial"
        TERRAIN = "TERRAIN", "Terrain"

    class ModeTransaction(models.TextChoices):
        LOCATION = "LOCATION", "Location"
        VENTE = "VENTE", "Vente"

    class StatutBien(models.TextChoices):
        DISPONIBLE = "DISPONIBLE", "Disponible"
        LOUE = "LOUE", "Loué"
        VENDU = "VENDU", "Vendu"
        EN_TRAVAUX = "EN_TRAVAUX", "En travaux"  # conservé

    proprietaire = models.ForeignKey(
        Proprietaire,
        on_delete=models.CASCADE,
        related_name="biens",
        verbose_name="propriétaire",
    )

    titre = models.CharField("titre", max_length=200)
    type = models.CharField("type de bien", max_length=20, choices=TypeBien.choices)
    mode_transaction = models.CharField(
        "mode de transaction",
        max_length=20,
        choices=ModeTransaction.choices,
        default=ModeTransaction.LOCATION,
    )
    adresse = models.CharField("adresse", max_length=255)
    surface = models.FloatField("surface (m²)", validators=[validate_surface])

    # Nombre de pièces : nullable pour les terrains
    nombre_pieces = models.IntegerField(
        "nombre de pièces",
        null=True,
        blank=True,
        validators=[validate_nombre_pieces],
    )

    # Loyer mensuel : nullable car non utilisé pour la vente
    loyer_mensuel = models.DecimalField(
        "loyer mensuel",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[validate_loyer_mensuel],
    )

    # Prix de vente : nullable car non utilisé pour la location
    prix = models.DecimalField(
        "prix de vente",
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[PositiveValueValidator("Le prix ne peut pas être négatif.")],
    )

    statut = models.CharField(
        "statut",
        max_length=20,
        choices=StatutBien.choices,
        default=StatutBien.DISPONIBLE,
    )

    photos = models.JSONField(
        "photos",
        null=True,
        blank=True,
        default=list,
        validators=[validate_photos],
    )

    class Meta:
        verbose_name = "Bien"
        verbose_name_plural = "Biens"
        ordering = ["-id"]
        constraints = [
            # Contraintes de positivité
            models.CheckConstraint(check=models.Q(surface__gte=0), name="bien_surface_positive"),
            models.CheckConstraint(
                check=models.Q(nombre_pieces__gte=0) | models.Q(nombre_pieces__isnull=True),
                name="bien_nombre_pieces_positive"
            ),
            models.CheckConstraint(
                check=models.Q(loyer_mensuel__gte=0) | models.Q(loyer_mensuel__isnull=True),
                name="bien_loyer_positive"
            ),
            models.CheckConstraint(
                check=models.Q(prix__gte=0) | models.Q(prix__isnull=True),
                name="bien_prix_positive"
            ),
            # Cohérence entre mode_transaction et champs financiers
            models.CheckConstraint(
                check=(
                    (models.Q(mode_transaction="LOCATION") & models.Q(loyer_mensuel__isnull=False) & models.Q(prix__isnull=True)) |
                    (models.Q(mode_transaction="VENTE") & models.Q(prix__isnull=False) & models.Q(loyer_mensuel__isnull=True))
                ),
                name="bien_coherence_location_vente"
            ),
            # Terrain : nombre_pieces nullable
            models.CheckConstraint(
                check=(
                    (models.Q(type="TERRAIN") & models.Q(nombre_pieces__isnull=True)) |
                    (models.Q(type__in=["APPARTEMENT", "MAISON", "LOCAL_COMMERCIAL"]) & models.Q(nombre_pieces__isnull=False))
                ),
                name="bien_terrain_pas_pieces"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.titre} — {self.get_statut_display()}"

    def clean(self):
        super().clean()
        # Validations supplémentaires (appelées par full_clean)
        if self.mode_transaction == self.ModeTransaction.LOCATION and self.loyer_mensuel is None:
            raise ValidationError({"loyer_mensuel": "Le loyer mensuel est obligatoire pour une location."})
        if self.mode_transaction == self.ModeTransaction.VENTE and self.prix is None:
            raise ValidationError({"prix": "Le prix est obligatoire pour une vente."})
        if self.type == self.TypeBien.TERRAIN and self.nombre_pieces is not None:
            raise ValidationError({"nombre_pieces": "Le nombre de pièces n'est pas applicable pour un terrain."})
        # Interdire de passer un bien en VENDU manuellement (cela doit se faire via contrat)
        # Cette vérification est faite dans le serializer.

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def est_disponible(self) -> bool:
        return self.statut == self.StatutBien.DISPONIBLE

    @property
    def est_loue(self) -> bool:
        return self.statut == self.StatutBien.LOUE

    @property
    def est_vendu(self) -> bool:
        return self.statut == self.StatutBien.VENDU