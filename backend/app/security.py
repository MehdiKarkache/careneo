"""Sécurité : mots de passe (Argon2id) et cookie de session.

Le cookie httpOnly contient un JWT signé (HS256) qui ne porte que l'identifiant de l'utilisateur ;
le rôle et l'entreprise sont relus en base à chaque requête (voir app.deps).
"""

import uuid
from datetime import timedelta

import jwt
from fastapi import Response
from pwdlib import PasswordHash

from app.config import settings
from app.domain import utcnow

_hasher = PasswordHash.recommended()
_JWT_ALGORITHM = "HS256"

# Haché factice : un email inconnu coûte autant qu'un mauvais mot de passe, pour que le temps
# de réponse ne révèle pas quels comptes existent.
_DUMMY_HASH = _hasher.hash("mot-de-passe-factice")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if password_hash is None:
        _hasher.verify(password, _DUMMY_HASH)
        return False
    return _hasher.verify(password, password_hash)


def create_session_token(user_id: uuid.UUID) -> str:
    now = utcnow()
    claims = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.session_ttl_minutes),
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=_JWT_ALGORITHM)


def read_session_token(token: str) -> uuid.UUID | None:
    """Identifiant de l'utilisateur si le jeton est authentique et non expiré, sinon None."""
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[_JWT_ALGORITHM],
            options={"require": ["sub", "iat", "exp"]},
        )
        return uuid.UUID(claims["sub"])
    except (jwt.InvalidTokenError, ValueError):
        return None


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_minutes * 60,
        httponly=True,  # inaccessible au JavaScript : protège le jeton d'une faille XSS
        secure=settings.cookie_secure,
        samesite="lax",  # non envoyé sur les requêtes POST d'un autre site : limite le CSRF
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
