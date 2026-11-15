"""Modèle de données SQLAlchemy, fidèle au diagramme de classes (docs/diagramme-de-classes.png).

Les méthodes du diagramme sont portées par les entités : User.has_role, Dock.can_fit,
Slot.overlaps et Slot.is_open, et les transitions de Booking (request, accept, reject, cancel),
qui enregistrent chacune un BookingEvent.

Les invariants critiques sont aussi garantis par PostgreSQL, pour tenir même face à des
requêtes concurrentes :
- deux créneaux actifs d'un même poste ne se chevauchent pas (contrainte d'exclusion) ;
- un créneau n'est attribué qu'à une seule demande (index unique partiel) ;
- un navire n'a qu'une demande active par créneau (index unique partiel).

Les relations sont en lazy="raise_on_sql" : en asynchrone, tout chargement doit être explicite
(selectinload, joinedload) ; une requête implicite lève une erreur claire au lieu d'un plantage.
"""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    MetaData,
    String,
    Table,
    Text,
    func,
    literal_column,
    text,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.domain import (
    BookingStatus,
    CompanyType,
    DockType,
    Role,
    SlotStatus,
    SlotUnavailable,
    VesselDoesNotFit,
    VesselType,
    dates_overlap,
    ensure_transition,
    today,
    utcnow,
)

# Noms de contraintes déterministes : les migrations sont stables et l'API peut reconnaître
# la contrainte violée.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UuidPk:
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid()
    )


def created_at_column() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now())


# ---------- Référentiel et utilisateurs ----------


class Company(UuidPk, Base):
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[CompanyType] = mapped_column(Enum(CompanyType, name="company_type"))


class User(UuidPk, Base):
    __tablename__ = "users"
    __table_args__ = (
        # Un admin n'appartient à aucune entreprise ; armateurs et chantiers à exactement une.
        CheckConstraint("(role = 'ADMIN') = (company_id IS NULL)", name="admin_without_company"),
    )

    email: Mapped[str] = mapped_column(String(254), unique=True)  # stocké en minuscules
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[Role] = mapped_column(Enum(Role, name="role"))
    company_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("companies.id"))

    company: Mapped[Company | None] = relationship(lazy="raise_on_sql")

    def has_role(self, *roles: Role) -> bool:
        return self.role in roles


class Port(UuidPk, Base):
    __tablename__ = "ports"

    name: Mapped[str] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(2))  # ISO 3166-1 alpha-2
    unlocode: Mapped[str] = mapped_column(String(5), unique=True)


# ---------- Chantiers ----------


class Shipyard(UuidPk, Base):
    __tablename__ = "shipyards"

    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    port_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ports.id"), index=True)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"), index=True)

    port: Mapped[Port] = relationship(lazy="raise_on_sql")
    company: Mapped[Company] = relationship(lazy="raise_on_sql")
    docks: Mapped[list["Dock"]] = relationship(
        back_populates="shipyard", order_by="Dock.name", lazy="raise_on_sql"
    )
    services: Mapped[list["Service"]] = relationship(
        back_populates="shipyard", order_by="Service.name", lazy="raise_on_sql"
    )


class Dock(UuidPk, Base):
    """Poste de carénage (forme de radoub, dock flottant, élévateur)."""

    __tablename__ = "docks"
    __table_args__ = (
        CheckConstraint(
            "max_length_m > 0 AND max_beam_m > 0 AND max_draft_m > 0", name="positive_dimensions"
        ),
    )

    shipyard_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shipyards.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    type: Mapped[DockType] = mapped_column(Enum(DockType, name="dock_type"))
    max_length_m: Mapped[float]
    max_beam_m: Mapped[float]
    max_draft_m: Mapped[float]

    shipyard: Mapped[Shipyard] = relationship(back_populates="docks", lazy="raise_on_sql")

    def can_fit(self, vessel: "Vessel") -> bool:
        """Règle de compatibilité : longueur, largeur et tirant d'eau dans les limites du poste."""
        return (
            vessel.length_m <= self.max_length_m
            and vessel.beam_m <= self.max_beam_m
            and vessel.draft_m <= self.max_draft_m
        )


class Service(UuidPk, Base):
    __tablename__ = "services"
    __table_args__ = (CheckConstraint("indicative_price >= 0", name="non_negative_price"),)

    shipyard_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shipyards.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(50))
    indicative_price: Mapped[int | None]  # euros HT

    shipyard: Mapped[Shipyard] = relationship(back_populates="services", lazy="raise_on_sql")


class Slot(UuidPk, Base):
    """Créneau de disponibilité d'un poste, en jours calendaires (bornes incluses)."""

    __tablename__ = "slots"
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="dates_in_order"),
        # Deux créneaux non fermés d'un même poste ne peuvent pas se chevaucher.
        ExcludeConstraint(
            (literal_column("dock_id"), "="),
            (literal_column("daterange(start_date, end_date, '[]')"), "&&"),
            name="ex_slots_no_overlap",
            using="gist",
            where=text("status <> 'CLOSED'"),
        ),
        Index("ix_slots_dock_id_start_date", "dock_id", "start_date"),
    )

    dock_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("docks.id"))
    start_date: Mapped[date]
    end_date: Mapped[date]
    status: Mapped[SlotStatus] = mapped_column(
        Enum(SlotStatus, name="slot_status"), default=SlotStatus.OPEN
    )

    dock: Mapped[Dock] = relationship(lazy="raise_on_sql")

    def __init__(self, **kwargs: Any) -> None:
        # Un créneau naît ouvert dès sa construction (le default de colonne n'agit qu'à l'INSERT).
        kwargs.setdefault("status", SlotStatus.OPEN)
        super().__init__(**kwargs)

    def overlaps(self, start: date, end: date) -> bool:
        return dates_overlap(self.start_date, self.end_date, start, end)

    def is_open(self) -> bool:
        return self.status == SlotStatus.OPEN

    def has_started(self) -> bool:
        return self.start_date <= today()


# ---------- Navires ----------


class Vessel(UuidPk, Base):
    __tablename__ = "vessels"
    __table_args__ = (
        CheckConstraint("imo ~ '^[0-9]{7}$'", name="imo_format"),
        CheckConstraint("length_m > 0 AND beam_m > 0 AND draft_m > 0", name="positive_dimensions"),
        CheckConstraint("gross_tonnage >= 0", name="non_negative_tonnage"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    imo: Mapped[str] = mapped_column(String(7), unique=True)
    type: Mapped[VesselType] = mapped_column(Enum(VesselType, name="vessel_type"))
    length_m: Mapped[float]
    beam_m: Mapped[float]
    draft_m: Mapped[float]
    gross_tonnage: Mapped[int | None]

    company: Mapped[Company] = relationship(lazy="raise_on_sql")


# ---------- Réservations ----------

booking_services = Table(
    "booking_services",
    Base.metadata,
    Column("booking_id", ForeignKey("bookings.id", ondelete="CASCADE"), primary_key=True),
    Column("service_id", ForeignKey("services.id"), primary_key=True),
)


class Booking(UuidPk, Base):
    """Demande de réservation d'un créneau. Porte la machine à états (voir app.domain)."""

    __tablename__ = "bookings"
    __table_args__ = (
        Index(
            "uq_bookings_slot_accepted",
            "slot_id",
            unique=True,
            postgresql_where=text("status = 'ACCEPTED'"),
        ),
        Index(
            "uq_bookings_vessel_slot_active",
            "vessel_id",
            "slot_id",
            unique=True,
            postgresql_where=text("status IN ('PENDING', 'ACCEPTED')"),
        ),
        Index("ix_bookings_slot_id_status", "slot_id", "status"),
    )

    vessel_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vessels.id"), index=True)
    slot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("slots.id"))
    requested_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus, name="booking_status"), default=BookingStatus.PENDING
    )
    message: Mapped[str | None] = mapped_column(Text)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_column()
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    vessel: Mapped[Vessel] = relationship(lazy="raise_on_sql")
    slot: Mapped[Slot] = relationship(lazy="raise_on_sql")
    requested_by: Mapped[User] = relationship(lazy="raise_on_sql")
    services: Mapped[list[Service]] = relationship(
        secondary=booking_services, order_by=Service.name, lazy="raise_on_sql"
    )
    events: Mapped[list["BookingEvent"]] = relationship(
        back_populates="booking",
        cascade="all, delete-orphan",
        order_by="BookingEvent.created_at",
        lazy="raise_on_sql",
    )

    @classmethod
    def request(
        cls,
        *,
        vessel: Vessel,
        slot: Slot,
        services: list[Service],
        by: User,
        message: str | None = None,
    ) -> "Booking":
        """Crée une demande PENDING si le créneau est réservable et si le navire entre dans
        le poste. Le créneau doit être chargé avec son poste."""
        if not slot.is_open() or slot.has_started():
            raise SlotUnavailable("Ce créneau n'est plus réservable")
        if not slot.dock.can_fit(vessel):
            raise VesselDoesNotFit(
                f"Le navire {vessel.name} dépasse les dimensions du poste {slot.dock.name}"
            )
        booking = cls(
            vessel=vessel,
            slot=slot,
            services=services,
            requested_by=by,
            message=message,
            status=BookingStatus.PENDING,
        )
        booking.events.append(
            BookingEvent(from_status=None, to_status=BookingStatus.PENDING, actor=by)
        )
        return booking

    def accept(self, by: User) -> None:
        """PENDING → ACCEPTED ; le créneau passe BOOKED. Le créneau doit être chargé."""
        ensure_transition(self.status, BookingStatus.ACCEPTED)
        if not self.slot.is_open():
            raise SlotUnavailable("Ce créneau est déjà attribué")
        self._record(BookingStatus.ACCEPTED, by)
        self.slot.status = SlotStatus.BOOKED

    def reject(self, by: User, reason: str) -> None:
        """PENDING → REJECTED, avec un motif. Le créneau reste ouvert."""
        self._record(BookingStatus.REJECTED, by, comment=reason)
        self.rejection_reason = reason

    def cancel(self, by: User) -> None:
        """PENDING → CANCELLED, à l'initiative de l'armateur."""
        self._record(BookingStatus.CANCELLED, by)

    def _record(self, target: BookingStatus, by: User, comment: str | None = None) -> None:
        """Applique une transition autorisée et l'historise dans un BookingEvent."""
        ensure_transition(self.status, target)
        self.events.append(
            BookingEvent(from_status=self.status, to_status=target, actor=by, comment=comment)
        )
        if self.status == BookingStatus.PENDING:
            self.decided_at = utcnow()
        self.status = target


class BookingEvent(UuidPk, Base):
    """Historique d'une réservation : quelle transition, par qui et quand."""

    __tablename__ = "booking_events"

    booking_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), index=True
    )
    from_status: Mapped[BookingStatus | None] = mapped_column(
        Enum(BookingStatus, name="booking_status")
    )
    to_status: Mapped[BookingStatus] = mapped_column(Enum(BookingStatus, name="booking_status"))
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_column()

    booking: Mapped[Booking] = relationship(back_populates="events", lazy="raise_on_sql")
    actor: Mapped[User] = relationship(lazy="raise_on_sql")
