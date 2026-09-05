from rest_framework import serializers
from django.utils import timezone
from .models import Contrat
from bien.models import Bien


class ContratSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contrat
        fields = [
            "id", "bien", "locataire", "type_contrat",
            "date_debut", "date_fin",
            "loyer", "depot_garantie", "prix",
            "statut", "document_pdf", "date_creation",
        ]
        read_only_fields = ["id", "date_creation"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtrer les biens disponibles pour la création
        if not self.instance:
            self.fields['bien'].queryset = Bien.objects.filter(
                statut=Bien.StatutBien.DISPONIBLE
            ).select_related('proprietaire__user')

    def validate(self, attrs):
        instance = self.instance
        type_contrat = attrs.get("type_contrat", getattr(instance, "type_contrat", None))
        statut = attrs.get("statut", getattr(instance, "statut", None))
        bien = attrs.get("bien", getattr(instance, "bien", None))
        locataire = attrs.get("locataire", getattr(instance, "locataire", None))

        # --- Pré‑remplissage automatique (création uniquement) ---
        if not instance and bien:
            if type_contrat == Contrat.TypeContrat.LOCATION:
                attrs.setdefault('loyer', bien.loyer_mensuel)
                if bien.loyer_mensuel:
                    attrs.setdefault('depot_garantie', bien.loyer_mensuel * 2)
                else:
                    attrs.setdefault('depot_garantie', 0)
            elif type_contrat == Contrat.TypeContrat.ACHAT:
                attrs.setdefault('prix', bien.prix)
                attrs.setdefault('date_debut', timezone.now().date())
                # Pour un achat, la date de fin n'est pas utilisée
                attrs['date_fin'] = None

        # --- 1. Cohérence type_contrat / champs financiers ---
        if type_contrat == Contrat.TypeContrat.LOCATION:
            loyer = attrs.get("loyer", getattr(instance, "loyer", None))
            depot = attrs.get("depot_garantie", getattr(instance, "depot_garantie", None))
            prix = attrs.get("prix", getattr(instance, "prix", None))
            if loyer is None:
                raise serializers.ValidationError({"loyer": "Le loyer est obligatoire pour une location."})
            if depot is None:
                raise serializers.ValidationError({"depot_garantie": "Le dépôt de garantie est obligatoire pour une location."})
            if prix is not None:
                raise serializers.ValidationError({"prix": "Le prix n'est pas utilisé pour une location."})

        elif type_contrat == Contrat.TypeContrat.ACHAT:
            prix = attrs.get("prix", getattr(instance, "prix", None))
            if prix is None:
                raise serializers.ValidationError({"prix": "Le prix est obligatoire pour un achat."})
            if "loyer" in attrs and attrs["loyer"] is not None:
                raise serializers.ValidationError({"loyer": "Le loyer n'est pas utilisé pour un achat."})
            if "depot_garantie" in attrs and attrs["depot_garantie"] is not None:
                raise serializers.ValidationError({"depot_garantie": "Le dépôt de garantie n'est pas utilisé pour un achat."})

        # --- 2. Vérifier que le bien est compatible avec le type de contrat ---
        if bien:
            if type_contrat == Contrat.TypeContrat.LOCATION and bien.mode_transaction != Bien.ModeTransaction.LOCATION:
                raise serializers.ValidationError({"bien": "Ce bien n'est pas proposé à la location."})
            if type_contrat == Contrat.TypeContrat.ACHAT and bien.mode_transaction != Bien.ModeTransaction.VENTE:
                raise serializers.ValidationError({"bien": "Ce bien n'est pas proposé à la vente."})

        # --- 3. Vérifier que le bien est disponible (pour une création) ---
        if not instance:
            if bien and bien.statut != Bien.StatutBien.DISPONIBLE:
                raise serializers.ValidationError({"bien": "Le bien n'est pas disponible (il est déjà loué ou vendu)."})
            if locataire and not hasattr(locataire, 'user'):
                raise serializers.ValidationError({"locataire": "Le locataire doit être un utilisateur."})

        # --- 4. Validation des transitions de statut (pour mise à jour) ---
        if instance:
            ancien_statut = instance.statut
            nouveau_statut = attrs.get("statut", ancien_statut)

            if "type_contrat" in attrs and attrs["type_contrat"] != instance.type_contrat:
                raise serializers.ValidationError({"type_contrat": "Le type de contrat ne peut pas être modifié."})
            if "bien" in attrs and attrs["bien"] != instance.bien:
                raise serializers.ValidationError({"bien": "Le bien associé ne peut pas être modifié."})
            if "locataire" in attrs and attrs["locataire"] != instance.locataire:
                raise serializers.ValidationError({"locataire": "Le locataire ne peut pas être modifié."})

            if ancien_statut == Contrat.StatutContrat.VENDU:
                raise serializers.ValidationError({"statut": "Un contrat vendu ne peut pas être modifié."})
            if ancien_statut in (Contrat.StatutContrat.RESILIE, Contrat.StatutContrat.TERMINE):
                if nouveau_statut != ancien_statut:
                    raise serializers.ValidationError({"statut": "Un contrat résilié ou terminé ne peut pas changer de statut."})
            if ancien_statut == Contrat.StatutContrat.ACTIF:
                if type_contrat == Contrat.TypeContrat.LOCATION:
                    if nouveau_statut not in (Contrat.StatutContrat.RESILIE, Contrat.StatutContrat.TERMINE):
                        raise serializers.ValidationError({"statut": "Un contrat de location actif ne peut devenir que RESILIE ou TERMINE."})
                elif type_contrat == Contrat.TypeContrat.ACHAT:
                    if nouveau_statut != Contrat.StatutContrat.VENDU:
                        raise serializers.ValidationError({"statut": "Un contrat d'achat actif ne peut devenir que VENDU."})

        return attrs

    def create(self, validated_data):
        return super().create(validated_data)