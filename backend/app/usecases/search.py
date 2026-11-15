"""Recherche de créneaux : le Shipyard.searchSlots du diagramme, appliqué en une seule requête
à tous les chantiers d'un port."""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager

from app.domain import ACTIVE_STATUSES
from app.models import Booking, Dock, Shipyard, Slot, Vessel


async def search_compatible_slots(
    session: AsyncSession, *, port_id: uuid.UUID, vessel: Vessel, start: date, end: date
) -> list[tuple[Slot, uuid.UUID | None]]:
    """Créneaux ouverts du port, qui chevauchent [start, end], pas encore commencés et dont le
    poste accepte le navire, triés par date de début. Chaque créneau est accompagné de la demande
    active que le navire y a déjà, le cas échéant."""
    slots = (
        await session.scalars(
            select(Slot)
            .join(Slot.dock)
            .join(Dock.shipyard)
            .join(Shipyard.port)
            .where(
                Shipyard.port_id == port_id,
                Slot.is_open(),
                ~Slot.has_started(),
                Slot.overlaps(start, end),
                Dock.can_fit(vessel),  # la règle du poste, traduite en SQL
            )
            .options(
                contains_eager(Slot.dock)
                .contains_eager(Dock.shipyard)
                .contains_eager(Shipyard.port),
                contains_eager(Slot.dock)
                .contains_eager(Dock.shipyard)
                .selectinload(Shipyard.services),
            )
            .order_by(Slot.start_date, Shipyard.name, Dock.name)
        )
    ).all()
    if not slots:
        return []

    active_requests = await session.execute(
        select(Booking.slot_id, Booking.id).where(
            Booking.vessel_id == vessel.id,
            Booking.slot_id.in_([slot.id for slot in slots]),
            Booking.status.in_(ACTIVE_STATUSES),
        )
    )
    existing = dict(active_requests.all())
    return [(slot, existing.get(slot.id)) for slot in slots]
