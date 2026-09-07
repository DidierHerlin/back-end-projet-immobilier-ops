# api/validators.py
"""
Validateurs de mot de passe personnalisés.

RG-02 : Le mot de passe doit respecter une politique de complexité minimale
        (8 caractères, majuscule, chiffre).

Ce validateur complète (et ne remplace pas) les validateurs Django standards
déclarés dans AUTH_PASSWORD_VALIDATORS (settings.py) :
- MinimumLengthValidator gère déjà la longueur minimale (8 caractères).
- ComplexPasswordValidator (ci-dessous) gère la présence d'une majuscule
  et d'un chiffre, non couverte par les validateurs Django par défaut.
"""

import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class ComplexPasswordValidator:
    """
    Vérifie que le mot de passe contient au moins :
    - une lettre majuscule
    - un chiffre

    RG-02 (cahier des charges) : "Le mot de passe doit respecter une
    politique de complexité minimale (8 caractères, majuscule, chiffre)."
    """

    def validate(self, password, user=None):
        errors = []

        if not re.search(r"[A-Z]", password):
            errors.append(
                ValidationError(
                    _("Le mot de passe doit contenir au moins une lettre majuscule."),
                    code="password_no_upper",
                )
            )

        if not re.search(r"[0-9]", password):
            errors.append(
                ValidationError(
                    _("Le mot de passe doit contenir au moins un chiffre."),
                    code="password_no_digit",
                )
            )

        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return _(
            "Votre mot de passe doit contenir au moins 8 caractères, "
            "dont une lettre majuscule et un chiffre."
        )