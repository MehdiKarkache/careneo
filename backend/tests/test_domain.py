"""Règles métier pures : aucune base de données n'est nécessaire."""

from datetime import date, timedelta

import pytest

from app.domain import (
    BookingStatus,
    InvalidTransition,
    SlotStatus,
    SlotUnavailable,
    VesselDoesNotFit,
    ensure_transition,
    is_valid_imo,
    today,
)
from app.models import Booking, Dock, Slot, User, Vessel


@pytest.mark.parametrize("imo", ["9421001", "9512343", "9706542", "9334014"])
def test_valid_imo_numbers(imo: str) -> None:
    assert is_valid_imo(imo)


@pytest.mark.parametrize("imo", ["9421002", "942100", "94210011", "abcdefg", "٩٤٢١٠٠١"])
def test_invalid_imo_numbers(imo: str) -> None:
    assert not is_valid_imo(imo)


def test_dock_compatibility_bounds_are_inclusive() -> None:
    dock = Dock(max_length_m=200, max_beam_m=30, max_draft_m=8)
    assert dock.can_fit(Vessel(length_m=200, beam_m=30, draft_m=8))
    assert not dock.can_fit(Vessel(length_m=200.1, beam_m=30, draft_m=8))
    assert not dock.can_fit(Vessel(length_m=150, beam_m=30, draft_m=8.2))


def test_slot_overlap_bounds_are_inclusive() -> None:
    slot = Slot(start_date=date(2030, 3, 1), end_date=date(2030, 3, 12))
    assert slot.is_open()
    assert slot.overlaps(date(2030, 3, 12), date(2030, 3, 20))
    assert slot.overlaps(date(2030, 2, 1), date(2030, 3, 1))
    assert not slot.overlaps(date(2030, 3, 13), date(2030, 3, 20))


def test_transition_table() -> None:
    for target in (BookingStatus.ACCEPTED, BookingStatus.REJECTED, BookingStatus.CANCELLED):
        ensure_transition(BookingStatus.PENDING, target)
    with pytest.raises(InvalidTransition, match=r"Demande déjà traitée \(statut : refusée\)"):
        ensure_transition(BookingStatus.REJECTED, BookingStatus.ACCEPTED)
    with pytest.raises(InvalidTransition):
        ensure_transition(BookingStatus.ACCEPTED, BookingStatus.CANCELLED)


def _scene() -> tuple[User, User, Slot, Vessel]:
    dock = Dock(name="Forme 1", max_length_m=200, max_beam_m=30, max_draft_m=8)
    start = today() + timedelta(days=10)
    slot = Slot(dock=dock, start_date=start, end_date=start + timedelta(days=11))
    vessel = Vessel(name="Ferry", length_m=150, beam_m=25, draft_m=6)
    return User(name="Armateur"), User(name="Chantier"), slot, vessel


def test_accepting_books_the_slot_and_records_each_transition() -> None:
    owner, yard, slot, vessel = _scene()
    booking = Booking.request(vessel=vessel, slot=slot, services=[], by=owner)
    assert booking.status == BookingStatus.PENDING
    booking.accept(by=yard)

    assert booking.status == BookingStatus.ACCEPTED
    assert slot.status == SlotStatus.BOOKED
    assert booking.decided_at is not None
    assert [(e.from_status, e.to_status, e.actor) for e in booking.events] == [
        (None, BookingStatus.PENDING, owner),
        (BookingStatus.PENDING, BookingStatus.ACCEPTED, yard),
    ]
    with pytest.raises(InvalidTransition):
        booking.cancel(by=owner)


def test_rejecting_keeps_the_slot_open_and_stores_the_reason() -> None:
    owner, yard, slot, vessel = _scene()
    booking = Booking.request(vessel=vessel, slot=slot, services=[], by=owner)
    booking.reject(by=yard, reason="Poste en maintenance")
    assert booking.status == BookingStatus.REJECTED
    assert booking.rejection_reason == booking.events[-1].comment == "Poste en maintenance"
    assert slot.status == SlotStatus.OPEN


def test_a_request_needs_a_bookable_slot_and_a_compatible_dock() -> None:
    owner, _, slot, vessel = _scene()
    with pytest.raises(VesselDoesNotFit):
        Booking.request(
            vessel=Vessel(name="Géant", length_m=250, beam_m=25, draft_m=6),
            slot=slot,
            services=[],
            by=owner,
        )

    slot.status = SlotStatus.CLOSED
    with pytest.raises(SlotUnavailable):
        Booking.request(vessel=vessel, slot=slot, services=[], by=owner)

    started = Slot(dock=slot.dock, start_date=today(), end_date=today() + timedelta(days=5))
    with pytest.raises(SlotUnavailable):
        Booking.request(vessel=vessel, slot=started, services=[], by=owner)
