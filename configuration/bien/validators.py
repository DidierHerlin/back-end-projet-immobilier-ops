from __future__ import annotations
from typing import Any
from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible

@deconstructible
class PositiveValueValidator:
    default_message = "Cette valeur ne peut pas être négative."
    code = "negative_value"
    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.default_message
    def __call__(self, value: Any) -> None:
        if value is not None and value < 0:
            raise ValidationError(self.message, code=self.code)
    def __eq__(self, other: object) -> bool:
        return isinstance(other, PositiveValueValidator) and self.message == other.message

@deconstructible
class PhotosListValidator:
    message_type = "Le champ 'photos' doit être une liste d'URLs."
    message_item = "Chaque photo doit être une chaîne de caractères (URL)."
    def __call__(self, value: Any) -> None:
        if not value:
            return
        if not isinstance(value, list):
            raise ValidationError(self.message_type, code="invalid_type")
        if not all(isinstance(item, str) for item in value):
            raise ValidationError(self.message_item, code="invalid_item")
    def __eq__(self, other: object) -> bool:
        return isinstance(other, PhotosListValidator)

validate_surface = PositiveValueValidator("La surface ne peut pas être négative.")
validate_nombre_pieces = PositiveValueValidator("Le nombre de pièces ne peut pas être négatif.")
validate_loyer_mensuel = PositiveValueValidator("Le loyer mensuel ne peut pas être négatif.")
validate_photos = PhotosListValidator()