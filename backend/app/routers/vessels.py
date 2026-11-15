import uuid

from sqlalchemy import select

from app import schemas
from app.access import get_owned_vessel
from app.db import commit
from app.deps import CurrentUser, SessionDep, allow
from app.domain import Role
from app.errors import Conflict
from app.models import Vessel
from app.routers import api_router

router = api_router("Navires")


@router.get(
    "/vessels",
    operation_id="listVessels",
    summary="Lister les navires de mon entreprise",
    **allow(Role.OWNER),
)
async def list_vessels(user: CurrentUser, session: SessionDep) -> list[schemas.Vessel]:
    vessels = await session.scalars(
        select(Vessel).where(Vessel.company_id == user.company_id).order_by(Vessel.name)
    )
    return [schemas.Vessel.model_validate(vessel) for vessel in vessels]


@router.post(
    "/vessels",
    operation_id="createVessel",
    summary="Créer un navire",
    status_code=201,
    **allow(Role.OWNER),
)
async def create_vessel(
    body: schemas.VesselInput, user: CurrentUser, session: SessionDep
) -> schemas.Vessel:
    if await session.scalar(select(Vessel.id).where(Vessel.imo == body.imo)):
        raise Conflict("Un navire avec ce numéro IMO existe déjà")
    vessel = Vessel(company_id=user.company_id, **body.model_dump())
    session.add(vessel)
    await commit(session)  # l'unicité de l'IMO est aussi garantie par la base
    return schemas.Vessel.model_validate(vessel)


@router.patch(
    "/vessels/{id}",
    operation_id="updateVessel",
    summary="Modifier un de mes navires",
    **allow(Role.OWNER),
)
async def update_vessel(
    id: uuid.UUID, body: schemas.VesselUpdate, user: CurrentUser, session: SessionDep
) -> schemas.Vessel:
    vessel = await get_owned_vessel(session, id, user)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(vessel, field, value)
    await commit(session)
    return schemas.Vessel.model_validate(vessel)
