import uuid
from datetime import date
from typing import Annotated

from fastapi import Query

from app import schemas
from app.access import get_owned_vessel
from app.deps import CurrentUser, SessionDep, allow
from app.domain import Role
from app.errors import NotFound, ValidationFailed
from app.models import Port
from app.routers import api_router
from app.usecases.search import search_compatible_slots

router = api_router("Recherche")


@router.get(
    "/search",
    operation_id="searchSlots",
    summary="Rechercher les créneaux ouverts et compatibles avec un navire",
    **allow(Role.OWNER),
)
async def search_slots(
    user: CurrentUser,
    session: SessionDep,
    port_id: Annotated[uuid.UUID, Query(alias="portId")],
    vessel_id: Annotated[
        uuid.UUID, Query(alias="vesselId", description="Navire de l'entreprise de l'utilisateur")
    ],
    start: Annotated[date, Query(alias="from")],
    end: Annotated[date, Query(alias="to", description="Postérieure ou égale à from")],
) -> list[schemas.SearchResult]:
    if end < start:
        raise ValidationFailed(details={"to": "La date de fin doit suivre la date de début"})
    vessel = await get_owned_vessel(session, vessel_id, user)
    if await session.get(Port, port_id) is None:
        raise NotFound("Port introuvable")
    matches = await search_compatible_slots(
        session, port_id=port_id, vessel=vessel, start=start, end=end
    )
    return [schemas.SearchResult.from_slot(slot, existing) for slot, existing in matches]
