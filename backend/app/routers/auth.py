from fastapi import Response
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from starlette.concurrency import run_in_threadpool

from app import schemas
from app.deps import ALL_ROLES, CurrentUser, SessionDep, allow
from app.errors import Unauthenticated
from app.models import User
from app.routers import api_router
from app.security import (
    clear_session_cookie,
    create_session_token,
    set_session_cookie,
    verify_password,
)

router = api_router("Authentification")


@router.post("/auth/login", operation_id="login", summary="Se connecter")
async def login(body: schemas.LoginInput, response: Response, session: SessionDep) -> schemas.Me:
    user = await session.scalar(
        select(User).options(joinedload(User.company)).where(User.email == body.email)
    )
    # Argon2 est volontairement coûteux : il est calculé hors de la boucle d'événements.
    password_ok = await run_in_threadpool(
        verify_password, body.password, user.password_hash if user else None
    )
    if user is None or not password_ok:
        raise Unauthenticated("Email ou mot de passe incorrect")
    set_session_cookie(response, create_session_token(user.id))
    return schemas.Me.model_validate(user)


@router.post(
    "/auth/logout",
    operation_id="logout",
    summary="Se déconnecter",
    status_code=204,
    response_class=Response,
)
async def logout() -> Response:
    response = Response(status_code=204)
    clear_session_cookie(response)
    return response


@router.get("/auth/me", operation_id="getMe", summary="Utilisateur connecté", **allow(*ALL_ROLES))
async def me(user: CurrentUser) -> schemas.Me:
    return schemas.Me.model_validate(user)
