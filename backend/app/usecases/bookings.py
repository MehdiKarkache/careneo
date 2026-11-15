"""Cycle de vie des réservations : demande de l'armateur, décision du chantier, annulation.

Concurrence : toute écriture sur une demande verrouille d'abord son créneau
(SELECT … FOR NO KEY UPDATE), puis la demande, puis le navire pour une acceptation. Cet ordre,
toujours le même, sérialise les décisions sur un même créneau sans risque d'interblocage :
- deux demandes rivales acceptées au même instant : une seule l'emporte, l'autre reçoit un 409 ;
- une demande créée pendant que son créneau est attribué attend la fin de l'attribution et voit
  le créneau occupé (verrou partagé FOR SHARE à la création) ;
- deux chantiers ne peuvent pas confirmer en même temps deux carénages qui se chevauchent pour
  un même navire (verrou sur le navire).
Les index uniques partiels de PostgreSQL restent le filet de sécurité final (app.db.commit).
"""

import uuid

from sqlalchemy import ColumnElement, exists, select, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.access import get_owned_vessel
from app.db import commit
from app.domain import (
    ACTIVE_STATUSES,
    AUTO_REJECTION_REASON,
    BookingStatus,
    Role,
    ensure_transition,
)
from app.errors import Conflict, Forbidden, NotFound, ValidationFailed
from app.models import Booking, BookingEvent, Dock, Service, Shipyard, Slot, User, Vessel

# Tout ce qu'il faut pour sérialiser une réservation, sans requête implicite.
BOOKING_LOAD = (
    joinedload(Booking.vessel),
    joinedload(Booking.requested_by).joinedload(User.company),
    joinedload(Booking.slot)
    .joinedload(Slot.dock)
    .joinedload(Dock.shipyard)
    .joinedload(Shipyard.port),
    selectinload(Booking.services),
)
DETAIL_LOAD = (*BOOKING_LOAD, selectinload(Booking.events).joinedload(BookingEvent.actor))

OVERLAPPING_CAREENING = (
    "Ce navire a déjà un carénage confirmé sur une période qui chevauche ce créneau"
)


# ---------- Consultation ----------


def visible_to(user: User) -> ColumnElement[bool]:
    """Armateur : les demandes de ses navires. Chantier : celles qui portent sur ses postes.
    Admin : toutes."""
    if user.has_role(Role.ADMIN):
        return true()
    if user.has_role(Role.OWNER):
        return Booking.vessel_id.in_(select(Vessel.id).where(Vessel.company_id == user.company_id))
    return Booking.slot_id.in_(
        select(Slot.id)
        .join(Slot.dock)
        .join(Dock.shipyard)
        .where(Shipyard.company_id == user.company_id)
    )


async def list_bookings(
    session: AsyncSession, user: User, status: BookingStatus | None
) -> list[Booking]:
    query = (
        select(Booking)
        .where(visible_to(user))
        .options(*BOOKING_LOAD)
        .order_by(Booking.created_at.desc())
    )
    if status is not None:
        query = query.where(Booking.status == status)
    return list(await session.scalars(query))


async def get_booking(
    session: AsyncSession, user: User, booking_id: uuid.UUID, *, with_events: bool = False
) -> Booking:
    """Réservation visible par l'utilisateur : 404 si elle n'existe pas, 403 si elle concerne
    d'autres entreprises. Après une écriture de la même requête, l'état en mémoire est déjà celui
    qui vient d'être validé : seules les relations manquantes sont chargées."""
    booking = await session.scalar(
        select(Booking)
        .where(Booking.id == booking_id, visible_to(user))
        .options(*(DETAIL_LOAD if with_events else BOOKING_LOAD))
    )
    if booking is None:
        if await session.scalar(select(Booking.id).where(Booking.id == booking_id)) is None:
            raise NotFound("Réservation introuvable")
        raise Forbidden("Cette réservation concerne une autre entreprise")
    return booking


# ---------- Demande de l'armateur ----------


async def create_booking(
    session: AsyncSession,
    user: User,
    *,
    vessel_id: uuid.UUID,
    slot_id: uuid.UUID,
    service_ids: list[uuid.UUID],
    message: str | None,
) -> uuid.UUID:
    vessel = await get_owned_vessel(session, vessel_id, user)
    slot = await session.scalar(
        select(Slot)
        .where(Slot.id == slot_id)
        .options(joinedload(Slot.dock))
        .with_for_update(read=True, of=Slot)  # attend une éventuelle attribution en cours
        .execution_options(populate_existing=True)
    )
    if slot is None:
        raise NotFound("Créneau introuvable")
    services = list(await session.scalars(select(Service).where(Service.id.in_(service_ids))))
    if len(services) != len(service_ids) or any(
        service.shipyard_id != slot.dock.shipyard_id for service in services
    ):
        raise ValidationFailed(
            details={"serviceIds": "Les services doivent appartenir au chantier du créneau"}
        )

    # Créneau réservable et navire compatible avec le poste (règles du domaine, sinon 409).
    booking = Booking.request(vessel=vessel, slot=slot, services=services, by=user, message=message)
    if await _has_active_request(session, vessel.id, slot.id):
        raise Conflict("Une demande est déjà en cours pour ce navire sur ce créneau")
    if await _has_confirmed_overlap(session, vessel.id, slot):
        raise Conflict(OVERLAPPING_CAREENING)
    session.add(booking)
    await commit(session)
    return booking.id


# ---------- Décisions ----------


async def accept_booking(session: AsyncSession, user: User, booking_id: uuid.UUID) -> None:
    """PENDING → ACCEPTED : le créneau passe BOOKED et les demandes rivales sur ce créneau sont
    refusées automatiquement, chaque transition étant historisée, le tout dans une transaction."""
    booking = await _lock_for_decision(session, user, booking_id, acting_as=Role.YARD)
    ensure_transition(booking.status, BookingStatus.ACCEPTED)
    await session.execute(
        select(Vessel.id).where(Vessel.id == booking.vessel_id).with_for_update(key_share=True)
    )
    if await _has_confirmed_overlap(session, booking.vessel_id, booking.slot):
        raise Conflict(OVERLAPPING_CAREENING)
    rivals = await session.scalars(
        select(Booking)
        .where(
            Booking.slot_id == booking.slot_id,
            Booking.status == BookingStatus.PENDING,
            Booking.id != booking.id,
        )
        .options(selectinload(Booking.events))
        .with_for_update(key_share=True, of=Booking)
    )
    booking.accept(by=user)
    for rival in rivals:
        rival.reject(by=user, reason=AUTO_REJECTION_REASON)
    await commit(session)


async def reject_booking(
    session: AsyncSession, user: User, booking_id: uuid.UUID, reason: str
) -> None:
    """PENDING → REJECTED avec un motif ; le créneau reste ouvert."""
    booking = await _lock_for_decision(session, user, booking_id, acting_as=Role.YARD)
    booking.reject(by=user, reason=reason)
    await commit(session)


async def cancel_booking(session: AsyncSession, user: User, booking_id: uuid.UUID) -> None:
    """PENDING → CANCELLED, par un utilisateur de l'entreprise propriétaire du navire."""
    booking = await _lock_for_decision(session, user, booking_id, acting_as=Role.OWNER)
    booking.cancel(by=user)
    await commit(session)


# ---------- Outils internes ----------


async def _lock_for_decision(
    session: AsyncSession, user: User, booking_id: uuid.UUID, *, acting_as: Role
) -> Booking:
    """Vérifie que l'utilisateur est partie prenante (chantier du créneau ou armateur du navire),
    puis verrouille le créneau et la demande, dans cet ordre, et renvoie la demande à jour."""
    parties = (
        await session.execute(
            select(Booking.slot_id, Shipyard.company_id, Vessel.company_id)
            .join(Booking.slot)
            .join(Slot.dock)
            .join(Dock.shipyard)
            .join(Booking.vessel)
            .where(Booking.id == booking_id)
        )
    ).one_or_none()
    if parties is None:
        raise NotFound("Réservation introuvable")
    slot_id, shipyard_company_id, vessel_company_id = parties
    if acting_as == Role.YARD and shipyard_company_id != user.company_id:
        raise Forbidden("Cette demande concerne le chantier d'une autre entreprise")
    if acting_as == Role.OWNER and vessel_company_id != user.company_id:
        raise Forbidden("Cette demande concerne le navire d'une autre entreprise")

    await session.execute(select(Slot.id).where(Slot.id == slot_id).with_for_update(key_share=True))
    booking = await session.scalar(
        select(Booking)
        .where(Booking.id == booking_id)
        .options(joinedload(Booking.slot), selectinload(Booking.events))
        .with_for_update(key_share=True, of=Booking)
        .execution_options(populate_existing=True)
    )
    assert booking is not None  # une demande n'est jamais supprimée
    return booking


async def _has_active_request(
    session: AsyncSession, vessel_id: uuid.UUID, slot_id: uuid.UUID
) -> bool:
    return bool(
        await session.scalar(
            select(
                exists().where(
                    Booking.vessel_id == vessel_id,
                    Booking.slot_id == slot_id,
                    Booking.status.in_(ACTIVE_STATUSES),
                )
            )
        )
    )


async def _has_confirmed_overlap(session: AsyncSession, vessel_id: uuid.UUID, slot: Slot) -> bool:
    """Le navire a-t-il déjà un carénage accepté sur une période qui chevauche ce créneau ?"""
    return bool(
        await session.scalar(
            select(
                exists().where(
                    Booking.vessel_id == vessel_id,
                    Booking.status == BookingStatus.ACCEPTED,
                    Booking.slot_id == Slot.id,
                    Slot.overlaps(slot.start_date, slot.end_date),
                )
            )
        )
    )
