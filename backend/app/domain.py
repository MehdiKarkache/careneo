"""Règles métier pures, sans base de données ni HTTP : énumérations du diagramme de classes,
machine à états des réservations, validation du numéro IMO et chevauchement de dates.

Les entités de app/models.py s'appuient sur ce module, testé unitairement.
"""

import re
from datetime import UTC, date, datetime
from enum import StrEnum
from zoneinfo import ZoneInfo

# Les dates de créneau sont des jours calendaires, exprimés dans le fuseau des chantiers.
BUSINESS_TZ = ZoneInfo("Europe/Paris")


class Role(StrEnum):
    OWNER = "OWNER"
    YARD = "YARD"
    ADMIN = "ADMIN"


class CompanyType(StrEnum):
    SHIPOWNER = "SHIPOWNER"
    SHIPYARD = "SHIPYARD"


class VesselType(StrEnum):
    FERRY = "FERRY"
    CONTAINER_SHIP = "CONTAINER_SHIP"
    TANKER = "TANKER"
    RO_RO = "RO_RO"
    OTHER = "OTHER"


class DockType(StrEnum):
    DRY_DOCK = "DRY_DOCK"
    FLOATING_DOCK = "FLOATING_DOCK"
    SHIPLIFT = "SHIPLIFT"


class SlotStatus(StrEnum):
    OPEN = "OPEN"
    BOOKED = "BOOKED"
    CLOSED = "CLOSED"


class BookingStatus(StrEnum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"  # prévu, non utilisé par le prototype
    COMPLETED = "COMPLETED"  # prévu, non utilisé par le prototype


STATUS_LABELS = {
    BookingStatus.PENDING: "en attente",
    BookingStatus.ACCEPTED: "acceptée",
    BookingStatus.REJECTED: "refusée",
    BookingStatus.CANCELLED: "annulée",
    BookingStatus.EXPIRED: "expirée",
    BookingStatus.COMPLETED: "terminée",
}

# Machine à états des réservations : statuts atteignables depuis chaque statut.
TRANSITIONS: dict[BookingStatus, frozenset[BookingStatus]] = {
    BookingStatus.PENDING: frozenset(
        {
            BookingStatus.ACCEPTED,
            BookingStatus.REJECTED,
            BookingStatus.CANCELLED,
            BookingStatus.EXPIRED,
        }
    ),
    BookingStatus.ACCEPTED: frozenset({BookingStatus.COMPLETED}),
}

# Une demande « active » réclame ou occupe son créneau.
ACTIVE_STATUSES = frozenset({BookingStatus.PENDING, BookingStatus.ACCEPTED})

AUTO_REJECTION_REASON = "Créneau attribué à une autre demande"


class DomainError(Exception):
    """Règle métier violée. L'API la traduit en 409 Conflict, avec ce message."""


class InvalidTransition(DomainError):
    pass


class SlotUnavailable(DomainError):
    pass


class VesselDoesNotFit(DomainError):
    pass


def ensure_transition(current: BookingStatus, target: BookingStatus) -> None:
    """Lève InvalidTransition si la machine à états interdit current → target."""
    if target in TRANSITIONS.get(current, frozenset()):
        return
    if current != BookingStatus.PENDING:
        raise InvalidTransition(f"Demande déjà traitée (statut : {STATUS_LABELS[current]})")
    raise InvalidTransition(
        f"Transition interdite : {STATUS_LABELS[current]} → {STATUS_LABELS[target]}"
    )


def dates_overlap(start_a: date, end_a: date, start_b: date, end_b: date) -> bool:
    """Chevauchement de deux périodes de jours calendaires, bornes incluses."""
    return start_a <= end_b and start_b <= end_a


_IMO_FORMAT = re.compile(r"[0-9]{7}")


def is_valid_imo(imo: str) -> bool:
    """Numéro IMO : 7 chiffres, dont le dernier est une clé de contrôle égale à la somme
    des 6 premiers pondérés par 7, 6, 5, 4, 3, 2, modulo 10."""
    if not _IMO_FORMAT.fullmatch(imo):
        return False
    weights = range(7, 1, -1)
    checksum = sum(int(digit) * weight for digit, weight in zip(imo[:6], weights, strict=True))
    return checksum % 10 == int(imo[6])


def utcnow() -> datetime:
    return datetime.now(UTC)


def today() -> date:
    """Date du jour dans le fuseau métier."""
    return datetime.now(BUSINESS_TZ).date()
