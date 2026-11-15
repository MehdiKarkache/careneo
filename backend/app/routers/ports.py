from sqlalchemy import select

from app import schemas
from app.deps import ALL_ROLES, SessionDep, allow
from app.models import Port
from app.routers import api_router

router = api_router("Référentiel")


@router.get("/ports", operation_id="listPorts", summary="Lister les ports", **allow(*ALL_ROLES))
async def list_ports(session: SessionDep) -> list[schemas.Port]:
    ports = await session.scalars(select(Port).order_by(Port.name))
    return [schemas.Port.model_validate(port) for port in ports]
