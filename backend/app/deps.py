"""Dépendances FastAPI : session de base de données, utilisateur connecté et garde de rôle."""

from typing import Annotated, Any

from fastapi import Depends
from fastapi.security import APIKeyCookie
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.config import settings
from app.db import get_session
from app.domain import Role
from app.errors import Forbidden, Unauthenticated
from app.models import User
from app.security import read_session_token

SessionDep = Annotated[AsyncSession, Depends(get_session)]

# Déclare le cookie de session comme schéma de sécurité de l'OpenAPI généré, comme le contrat.
_session_cookie = APIKeyCookie(
    name=settings.session_cookie_name, scheme_name="sessionCookie", auto_error=False
)


async def get_current_user(
    session: SessionDep, token: Annotated[str | None, Depends(_session_cookie)]
) -> User:
    """Utilisateur du cookie de session, relu en base (rôle et entreprise toujours à jour)."""
    user_id = read_session_token(token) if token else None
    if user_id is None:
        raise Unauthenticated()
    user = await session.scalar(
        select(User).options(joinedload(User.company)).where(User.id == user_id)
    )
    if user is None:
        raise Unauthenticated()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]

ALL_ROLES = tuple(Role)
ROLE_LABELS = {Role.OWNER: "armateur", Role.YARD: "chantier", Role.ADMIN: "administrateur"}


def allow(*roles: Role) -> dict[str, Any]:
    """Garde de rôle d'une route, à déplier dans son décorateur :
    `@router.get("/vessels", **allow(Role.OWNER))`.

    La garde est appliquée par une dépendance (401 sans session, 403 si mauvais rôle) et
    documentée dans l'OpenAPI généré (`x-roles`), que les tests comparent au contrat.
    """

    async def require_role(user: CurrentUser) -> None:
        if not user.has_role(*roles):
            allowed = " ou ".join(ROLE_LABELS[role] for role in roles)
            raise Forbidden(f"Action réservée aux comptes {allowed}")

    return {
        "dependencies": [Depends(require_role)],
        "openapi_extra": {"x-roles": [role.value for role in roles]},
    }
