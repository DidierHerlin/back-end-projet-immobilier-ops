from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import F, Q, UniqueConstraint
from bien.models import Bien
from utilisateur.models import Locataire


class Contrat(models.Model):
    class TypeContrat(models.TextChoices):
        LOCATION = "LOCATION", "Location"
        ACHAT = "ACHAT", "Achat"

    class StatutContrat(models.TextChoices):
        ACTIF = "ACTIF", "Actif"
        RESILIE = "RESILIE", "Résilié"
        TERMINE = "TERMINE", "Terminé"
        VENDU = "VENDU", "Vendu"  # pour l'achat

    bien = models.ForeignKey(
        Bien,
        on_delete=models.PROTECT,
        related_name="contrats",
        verbose_name="Bien concerné",
    )
    locataire = models.ForeignKey(
        Locataire,
        on_delete=models.PROTECT,
        related_name="contrats",
        verbose_name="Locataire / Acheteur",
    )

    type_contrat = models.CharField(
        "type de contrat",
        max_length=20,
        choices=TypeContrat.choices,
        default=TypeContrat.LOCATION,
    )

    date_debut = models.DateField("Date de début")
    date_fin = models.DateField("Date de fin", null=True, blank=True)  # Pour location

    # Champs pour la location
    loyer = models.DecimalField(
        "Loyer mensuel",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    depot_garantie = models.DecimalField(
        "Dépôt de garantie",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    # Champ pour l'achat
    prix = models.DecimalField(
        "Prix de vente",
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
    )

    statut = models.CharField(
        "statut",
        max_length=20,
        choices=StatutContrat.choices,
        default=StatutContrat.ACTIF,
        db_index=True,
    )

    document_pdf = models.CharField(
        max_length=255, null=True, blank=True, verbose_name="Chemin du document PDF"
    )
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")

    class Meta:
        db_table = "contrat"
        ordering = ["-date_creation"]
        verbose_name = "Contrat"
        verbose_name_plural = "Contrats"
        constraints = [
            # Cohérence type_contrat / champs financiers
            models.CheckConstraint(
                check=(
                    (models.Q(type_contrat="LOCATION") & models.Q(loyer__isnull=False) & models.Q(depot_garantie__isnull=False) & models.Q(prix__isnull=True)) |
                    (models.Q(type_contrat="ACHAT") & models.Q(prix__isnull=False) & models.Q(loyer__isnull=True) & models.Q(depot_garantie__isnull=True))
                ),
                name="contrat_coherence_location_achat"
            ),
            # Statuts autorisés selon type
            models.CheckConstraint(
                check=(
                    (models.Q(type_contrat="LOCATION") & models.Q(statut__in=["ACTIF", "RESILIE", "TERMINE"])) |
                    (models.Q(type_contrat="ACHAT") & models.Q(statut__in=["ACTIF", "VENDU"]))
                ),
                name="contrat_statut_autorise"
            ),
            # Pour location : date_fin obligatoire et > date_debut (sauf si null pour achat)
            models.CheckConstraint(
                check=(
                    (models.Q(type_contrat="LOCATION") & models.Q(date_fin__isnull=False) & models.Q(date_fin__gt=F("date_debut"))) |
                    (models.Q(type_contrat="ACHAT") & models.Q(date_fin__isnull=True))
                ),
                name="contrat_dates_location"
            ),
            # Montants positifs
            models.CheckConstraint(
                check=models.Q(loyer__gte=0) | models.Q(loyer__isnull=True),
                name="contrat_loyer_positive"
            ),
            models.CheckConstraint(
                check=models.Q(depot_garantie__gte=0) | models.Q(depot_garantie__isnull=True),
                name="contrat_depot_positive"
            ),
            models.CheckConstraint(
                check=models.Q(prix__gte=0) | models.Q(prix__isnull=True),
                name="contrat_prix_positive"
            ),
            # Un seul contrat ACTIF par bien (pour location comme pour achat)
            UniqueConstraint(
                fields=["bien"],
                condition=Q(statut="ACTIF"),
                name="rg13_un_seul_contrat_actif_par_bien",
            ),
        ]

    def __str__(self):
        return f"Contrat #{self.pk} — {self.get_type_contrat_display()} ({self.statut})"

    def clean(self):
        super().clean()
        # Validations métier supplémentaires
        if self.type_contrat == self.TypeContrat.LOCATION:
            if not self.date_fin:
                raise ValidationError({"date_fin": "La date de fin est obligatoire pour une location."})
            if self.date_fin <= self.date_debut:
                raise ValidationError({"date_fin": "La date de fin doit être postérieure à la date de début."})
            if self.loyer is None:
                raise ValidationError({"loyer": "Le loyer est obligatoire pour une location."})
            if self.depot_garantie is None:
                raise ValidationError({"depot_garantie": "Le dépôt de garantie est obligatoire pour une location."})
        elif self.type_contrat == self.TypeContrat.ACHAT:
            if self.prix is None:
                raise ValidationError({"prix": "Le prix est obligatoire pour un achat."})
            if self.date_fin is not None:
                raise ValidationError({"date_fin": "La date de fin n'est pas utilisée pour un achat."})

        # Vérifier que le bien est disponible
        if self.pk is None:  # création
            if self.bien.statut != Bien.StatutBien.DISPONIBLE:
                raise ValidationError({"bien": "Le bien n'est pas disponible (il est déjà loué ou vendu)."})
            # Vérifier que le bien a le bon mode de transaction
            if self.type_contrat == self.TypeContrat.LOCATION and self.bien.mode_transaction != Bien.ModeTransaction.LOCATION:
                raise ValidationError({"type_contrat": "Ce bien n'est pas proposé à la location."})
            if self.type_contrat == self.TypeContrat.ACHAT and self.bien.mode_transaction != Bien.ModeTransaction.VENTE:
                raise ValidationError({"type_contrat": "Ce bien n'est pas proposé à la vente."})

        # Vérifier les transitions de statut (mises à jour)
        if self.pk:
            ancien = Contrat.objects.get(pk=self.pk)
            if ancien.statut == self.StatutContrat.VENDU:
                raise ValidationError({"statut": "Un contrat vendu ne peut pas être modifié."})
            if ancien.statut == self.StatutContrat.TERMINE and self.statut != ancien.statut:
                raise ValidationError({"statut": "Un contrat terminé ne peut pas changer de statut."})
            if ancien.statut == self.StatutContrat.RESILIE and self.statut != ancien.statut:
                raise ValidationError({"statut": "Un contrat résilié ne peut pas changer de statut."})
            if self.statut == self.StatutContrat.ACTIF and ancien.statut != self.StatutContrat.ACTIF:
                # On ne réactive pas un contrat
                raise ValidationError({"statut": "Seul un contrat actif peut être modifié pour devenir résilié/terminé/vendu."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    # Méthodes de transition
    def resilier(self, *, save=True):
        if self.type_contrat != self.TypeContrat.LOCATION:
            raise ValueError("Seuls les contrats de location peuvent être résiliés.")
        if self.statut != self.StatutContrat.ACTIF:
            raise ValueError("Seul un contrat actif peut être résilié.")
        self.statut = self.StatutContrat.RESILIE
        if save:
            self.save(update_fields=["statut"])

    def terminer(self, *, save=True):
        if self.type_contrat != self.TypeContrat.LOCATION:
            raise ValueError("Seuls les contrats de location peuvent être terminés.")
        if self.statut != self.StatutContrat.ACTIF:
            raise ValueError("Seul un contrat actif peut être terminé.")
        self.statut = self.StatutContrat.TERMINE
        if save:
            self.save(update_fields=["statut"])

    def finaliser_vente(self, *, save=True):
        if self.type_contrat != self.TypeContrat.ACHAT:
            raise ValueError("Seuls les contrats d'achat peuvent être finalisés.")
        if self.statut != self.StatutContrat.ACTIF:
            raise ValueError("Seul un contrat actif peut être finalisé.")
        self.statut = self.StatutContrat.VENDU
        if save:
            self.save(update_fields=["statut"])

    @property
    def est_actif(self):
        return self.statut == self.StatutContrat.ACTIF