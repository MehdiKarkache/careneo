from sqlalchemy import func, select

from app import schemas
from app.deps import SessionDep, allow
from app.domain import BookingStatus, Role
from app.models import Booking, Dock, Shipyard, Slot
from app.routers import api_router

router = api_router("Admin")


@router.get(
    "/admin/stats",
    operation_id="getAdminStats",
    summary="Compteurs par statut et par chantier",
    **allow(Role.ADMIN),
)
async def get_admin_stats(session: SessionDep) -> schemas.AdminStats:
    by_status = await session.execute(select(Booking.status, func.count()).group_by(Booking.status))
    counts = dict(by_status.all())

    total = func.count(Booking.id)
    by_shipyard = await session.execute(
        select(Shipyard.id, Shipyard.name, total)
        .outerjoin(Dock, Dock.shipyard_id == Shipyard.id)
        .outerjoin(Slot, Slot.dock_id == Dock.id)
        .outerjoin(Booking, Booking.slot_id == Slot.id)
        .group_by(Shipyard.id, Shipyard.name)
        .order_by(total.desc(), Shipyard.name)
    )
    return schemas.AdminStats(
        by_status={status: counts.get(status, 0) for status in BookingStatus},
        by_shipyard=[
            schemas.ShipyardTotal(shipyard_id=shipyard_id, name=name, total=count)
            for shipyard_id, name, count in by_shipyard
        ],
    )
