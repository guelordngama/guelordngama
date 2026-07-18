"""Compatibilité ascendante : l'authentification vit désormais dans
`backend.security`. Ce module réexporte les symboles pour ne pas casser
d'éventuels imports existants.
"""
from .security import (  # noqa: F401
    decode_token,
    generate_token,
    hash_password,
    rate_limit,
    require_auth,
    verify_password,
)
