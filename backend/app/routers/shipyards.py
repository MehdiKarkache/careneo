import uuid
from typing import Annotated

from fastapi import Query
from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from app import schemas
from app.access import get_managed_dock, get_owned_shipyard
from app.db import commit
from app.deps import ALL_ROLES, CurrentUser, SessionDep, allow
from app.domain import Role, SlotStatus, today
from app.errors import Conflict, NotFound, ValidationFailed
from app.models import Service, Shipyard, Slot
from app.routers import api_router

router = api_router("Chantiers")


@router.get(
    "/shipyards",
    operation_id="listShipyards",
    summary="Lister les chantiers",
    **allow(*ALL_ROLES),
)
async def list_shipyards(
    user: CurrentUser,
    session: SessionDep,
    port_id: Annotated[uuid.UUID | None, Query(alias="portId")] = None,
) -> list[schemas.ShipyardSummary]:
    query = select(Shipyard).options(joinedload(Shipyard.port)).order_by(Shipyard.name)
    if user.has_role(Role.YARD):
        query = query.where(Shipyard.company_id == user.company_id)
    if port_id is not None:
        query = query.where(Shipyard.port_id == port_id)
    shipyards = await session.scalars(query)
    return [schemas.ShipyardSummary.model_validate(shipyard) for shipyard in shipyards]


@router.get(
    "/shipyards/{id}",
    operation_id="getShipyard",
    summary="Fiche d'un chantier (postes et services)",
    **allow(*ALL_ROLES),
)
async def get_shipyard(id: uuid.UUID, session: SessionDep) -> schemas.ShipyardDetail:
    shipyard = await session.scalar(
        select(Shipyard)
        .where(Shipyard.id == id)
        .options(
            joinedload(Shipyard.port),
            selectinload(Shipyard.docks),
            selectinload(Shipyard.services),
        )
    )
    if shipyard is None:
        raise NotFound("Chantier introuvable")
    return schemas.ShipyardDetail.model_validate(shipyard)


@router.post(
    "/shipyards/{id}/services",
    operation_id="createService",
    summary="Ajouter un service à mon chantier",
    status_code=201,
    **allow(Role.YARD),
)
async def create_service(
    id: uuid.UUID, body: schemas.ServiceInput, user: CurrentUser, session: SessionDep
) -> schemas.Service:
    shipyard = await get_owned_shipyard(session, id, user)
    service = Service(shipyard_id=shipyard.id, **body.model_dump())
    session.add(service)
    await commit(session)
    return schemas.Service.model_validate(service)


@router.get(
    "/docks/{id}/slots",
    operation_id="listDockSlots",
    summary="Lister les créneaux d'un poste",
    **allow(Role.YARD, Role.ADMIN),
)
async def list_dock_slots(
    id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> list[schemas.Slot]:
    dock = await get_managed_dock(session, id, user)
    slots = await session.scalars(
        select(Slot)
        .where(Slot.dock_id == dock.id, Slot.end_date >= today())
        .order_by(Slot.start_date)
    )
    return [schemas.Slot.model_validate(slot) for slot in slots]


@router.post(
    "/docks/{id}/slots",
    operation_id="createSlot",
    summary="Ouvrir un créneau sur un de mes postes",
    status_code=201,
    **allow(Role.YARD),
)
async def create_slot(
    id: uuid.UUID, body: schemas.SlotInput, user: CurrentUser, session: SessionDep
) -> schemas.Slot:
    dock = await get_managed_dock(session, id, user)
    if body.start_date <= today():
        raise ValidationFailed(details={"startDate": "Un créneau commence au plus tôt demain"})
    overlapping = await session.scalar(
        select(Slot.id)
        .where(
            Slot.dock_id == dock.id,
            Slot.status != SlotStatus.CLOSED,
            Slot.overlaps(body.start_date, body.end_date),
        )
        .limit(1)
    )
    if overlapping is not None:
        raise Conflict("Ce créneau chevauche un créneau existant du poste")
    slot = Slot(dock_id=dock.id, start_date=body.start_date, end_date=body.end_date)
    session.add(slot)
    await commit(session)  # la contrainte d'exclusion couvre deux créations simultanées
    return schemas.Slot.model_validate(slot)
