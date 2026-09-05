from __future__ import annotations
from typing import Any
from rest_framework import serializers
from utilisateur.models import Proprietaire, Utilisateur
from utilisateur.serializers import ProprietaireSimpleSerializer
from .models import Bien


class BienSerializer(serializers.ModelSerializer):
    proprietaire = ProprietaireSimpleSerializer(read_only=True)
    proprietaire_id = serializers.PrimaryKeyRelatedField(
        queryset=Proprietaire.objects.all(),
        source="proprietaire",
        write_only=True,
        required=False,
        help_text="Requis pour un agent ou administrateur ; interdit pour un propriétaire.",
    )

    class Meta:
        model = Bien
        fields = [
            "id", "proprietaire", "proprietaire_id",
            "titre", "type", "mode_transaction", "adresse", "surface",
            "nombre_pieces", "loyer_mensuel", "prix", "statut", "photos",
        ]
        read_only_fields = ["id"]

    def validate_surface(self, value: float) -> float:
        if value < 0:
            raise serializers.ValidationError("La surface ne peut pas être négative.")
        return value

    def validate_nombre_pieces(self, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise serializers.ValidationError("Le nombre de pièces ne peut pas être négatif.")
        return value

    def validate_loyer_mensuel(self, value) -> Any:
        if value is not None and value < 0:
            raise serializers.ValidationError("Le loyer mensuel ne peut pas être négatif.")
        return value

    def validate_prix(self, value) -> Any:
        if value is not None and value < 0:
            raise serializers.ValidationError("Le prix ne peut pas être négatif.")
        return value

    def validate_photos(self, value: list | None) -> list | None:
        if value is None:
            return value
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise serializers.ValidationError("Le champ 'photos' doit être une liste d'URLs (chaînes).")
        return value

    def validate_statut(self, value: str) -> str:
        request = self.context.get("request")
        est_admin = bool(request and getattr(request.user, "role", None) == Utilisateur.Role.ADMIN)

        if value in (Bien.StatutBien.LOUE, Bien.StatutBien.VENDU) and not est_admin:
            raise serializers.ValidationError(
                f"Le statut '{value}' est attribué automatiquement par un contrat et ne peut pas être défini manuellement."
            )
        return value

    def validate(self, attrs: dict) -> dict:
        request = self.context["request"]
        user = request.user

        # Vérifier que le propriétaire n'est pas spécifié par un propriétaire
        if user.role == Utilisateur.Role.PROPRIETAIRE and "proprietaire" in attrs:
            raise serializers.ValidationError({
                "proprietaire_id": "Vous n'êtes pas autorisé à spécifier un propriétaire : ce champ est automatiquement associé à votre compte."
            })

        creation = self.instance is None
        if creation and user.role in (Utilisateur.Role.AGENT, Utilisateur.Role.ADMIN) and "proprietaire" not in attrs:
            raise serializers.ValidationError({
                "proprietaire_id": "Ce champ est requis pour un agent ou un administrateur."
            })

        # Règles de cohérence mode_transaction / loyer / prix
        mode = attrs.get("mode_transaction", getattr(self.instance, "mode_transaction", None))
        loyer = attrs.get("loyer_mensuel", getattr(self.instance, "loyer_mensuel", None))
        prix = attrs.get("prix", getattr(self.instance, "prix", None))

        if mode == Bien.ModeTransaction.LOCATION:
            if loyer is None:
                raise serializers.ValidationError({"loyer_mensuel": "Le loyer mensuel est obligatoire pour une location."})
            if prix is not None:
                raise serializers.ValidationError({"prix": "Le prix ne doit pas être renseigné pour une location."})
        elif mode == Bien.ModeTransaction.VENTE:
            if prix is None:
                raise serializers.ValidationError({"prix": "Le prix est obligatoire pour une vente."})
            if loyer is not None:
                raise serializers.ValidationError({"loyer_mensuel": "Le loyer mensuel ne doit pas être renseigné pour une vente."})

        # Règle terrain : nombre_pieces doit être null
        type_bien = attrs.get("type", getattr(self.instance, "type", None))
        nombre_pieces = attrs.get("nombre_pieces", getattr(self.instance, "nombre_pieces", None))
        if type_bien == Bien.TypeBien.TERRAIN and nombre_pieces is not None:
            raise serializers.ValidationError({"nombre_pieces": "Le nombre de pièces n'est pas applicable pour un terrain."})
        if type_bien != Bien.TypeBien.TERRAIN and nombre_pieces is None:
            raise serializers.ValidationError({"nombre_pieces": "Le nombre de pièces est obligatoire pour ce type de bien."})

        # Restrictions sur la modification d'un bien selon son statut
        if self.instance:
            # Interdire toute modification pour les biens LOUE ou VENDU
            if self.instance.statut in (Bien.StatutBien.LOUE, Bien.StatutBien.VENDU):
                raise serializers.ValidationError(
                    "Ce bien est déjà loué ou vendu et ne peut pas être modifié."
                )
            # Les autres restrictions existantes (ex: proprietaire) sont déjà gérées
            # On peut garder les restrictions de champs spécifiques si nécessaires
            if "mode_transaction" in attrs and attrs["mode_transaction"] != self.instance.mode_transaction:
                # On autorise le changement de mode si le bien est disponible
                # (déjà vérifié par le statut)
                pass  # autorisé si le bien est disponible

        return attrs

    def create(self, validated_data: dict) -> Bien:
        request = self.context["request"]
        user = request.user

        if user.role == Utilisateur.Role.PROPRIETAIRE:
            try:
                validated_data["proprietaire"] = user.profil_proprietaire
            except Proprietaire.DoesNotExist as exc:
                raise serializers.ValidationError(
                    "Aucun profil propriétaire n'est associé à ce compte utilisateur."
                ) from exc

        return Bien.objects.create(**validated_data)

    def update(self, instance: Bien, validated_data: dict) -> Bien:
        request = self.context["request"]
        user = request.user

        if user.role == Utilisateur.Role.PROPRIETAIRE:
            validated_data.pop("proprietaire", None)

        return super().update(instance, validated_data)


class BienListSerializer(serializers.ModelSerializer):
    proprietaire = ProprietaireSimpleSerializer(read_only=True)

    class Meta:
        model = Bien
        fields = ["id", "titre", "type", "mode_transaction", "adresse", "loyer_mensuel", "prix", "statut", "proprietaire"]