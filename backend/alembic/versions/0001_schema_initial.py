"""Schéma initial : entités du diagramme de classes et invariants garantis par PostgreSQL.

Revision ID: 0001
Revises:
Create Date: 2026-11-15

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Types énumérés PostgreSQL : créés une seule fois, puis partagés entre les tables.
company_type = postgresql.ENUM("SHIPOWNER", "SHIPYARD", name="company_type", create_type=False)
role = postgresql.ENUM("OWNER", "YARD", "ADMIN", name="role", create_type=False)
vessel_type = postgresql.ENUM(
    "FERRY", "CONTAINER_SHIP", "TANKER", "RO_RO", "OTHER", name="vessel_type", create_type=False
)
dock_type = postgresql.ENUM(
    "DRY_DOCK", "FLOATING_DOCK", "SHIPLIFT", name="dock_type", create_type=False
)
slot_status = postgresql.ENUM("OPEN", "BOOKED", "CLOSED", name="slot_status", create_type=False)
booking_status = postgresql.ENUM(
    "PENDING",
    "ACCEPTED",
    "REJECTED",
    "CANCELLED",
    "EXPIRED",
    "COMPLETED",
    name="booking_status",
    create_type=False,
)
ENUMS = (company_type, role, vessel_type, dock_type, slot_status, booking_status)


def uuid_pk() -> sa.Column:
    return sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False)


def created_at() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )


def upgrade() -> None:
    # btree_gist permet de combiner « = » sur un UUID et « && » sur une plage de dates
    # dans la contrainte d'exclusion des créneaux.
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    bind = op.get_bind()
    for enum in ENUMS:
        enum.create(bind, checkfirst=True)

    op.create_table(
        "companies",
        uuid_pk(),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("type", company_type, nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_companies")),
    )
    op.create_table(
        "ports",
        uuid_pk(),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=False),
        sa.Column("unlocode", sa.String(length=5), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ports")),
        sa.UniqueConstraint("unlocode", name=op.f("uq_ports_unlocode")),
    )
    op.create_table(
        "users",
        uuid_pk(),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("role", role, nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "(role = 'ADMIN') = (company_id IS NULL)", name=op.f("ck_users_admin_without_company")
        ),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"], name=op.f("fk_users_company_id_companies")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "shipyards",
        uuid_pk(),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("port_id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"], name=op.f("fk_shipyards_company_id_companies")
        ),
        sa.ForeignKeyConstraint(["port_id"], ["ports.id"], name=op.f("fk_shipyards_port_id_ports")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shipyards")),
    )
    op.create_index(op.f("ix_shipyards_company_id"), "shipyards", ["company_id"])
    op.create_index(op.f("ix_shipyards_port_id"), "shipyards", ["port_id"])

    op.create_table(
        "docks",
        uuid_pk(),
        sa.Column("shipyard_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("type", dock_type, nullable=False),
        sa.Column("max_length_m", sa.Double(), nullable=False),
        sa.Column("max_beam_m", sa.Double(), nullable=False),
        sa.Column("max_draft_m", sa.Double(), nullable=False),
        sa.CheckConstraint(
            "max_length_m > 0 AND max_beam_m > 0 AND max_draft_m > 0",
            name=op.f("ck_docks_positive_dimensions"),
        ),
        sa.ForeignKeyConstraint(
            ["shipyard_id"], ["shipyards.id"], name=op.f("fk_docks_shipyard_id_shipyards")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_docks")),
    )
    op.create_index(op.f("ix_docks_shipyard_id"), "docks", ["shipyard_id"])

    op.create_table(
        "services",
        uuid_pk(),
        sa.Column("shipyard_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("indicative_price", sa.Integer(), nullable=True),
        sa.CheckConstraint("indicative_price >= 0", name=op.f("ck_services_non_negative_price")),
        sa.ForeignKeyConstraint(
            ["shipyard_id"], ["shipyards.id"], name=op.f("fk_services_shipyard_id_shipyards")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_services")),
    )
    op.create_index(op.f("ix_services_shipyard_id"), "services", ["shipyard_id"])

    op.create_table(
        "slots",
        uuid_pk(),
        sa.Column("dock_id", sa.Uuid(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", slot_status, nullable=False),
        sa.CheckConstraint("end_date >= start_date", name=op.f("ck_slots_dates_in_order")),
        # Deux créneaux non fermés d'un même poste ne peuvent pas se chevaucher (bornes incluses).
        postgresql.ExcludeConstraint(
            (sa.literal_column("dock_id"), "="),
            (sa.literal_column("daterange(start_date, end_date, '[]')"), "&&"),
            where=sa.text("status <> 'CLOSED'"),
            using="gist",
            name="ex_slots_no_overlap",
        ),
        sa.ForeignKeyConstraint(["dock_id"], ["docks.id"], name=op.f("fk_slots_dock_id_docks")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_slots")),
    )
    op.create_index("ix_slots_dock_id_start_date", "slots", ["dock_id", "start_date"])

    op.create_table(
        "vessels",
        uuid_pk(),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("imo", sa.String(length=7), nullable=False),
        sa.Column("type", vessel_type, nullable=False),
        sa.Column("length_m", sa.Double(), nullable=False),
        sa.Column("beam_m", sa.Double(), nullable=False),
        sa.Column("draft_m", sa.Double(), nullable=False),
        sa.Column("gross_tonnage", sa.Integer(), nullable=True),
        sa.CheckConstraint("imo ~ '^[0-9]{7}$'", name=op.f("ck_vessels_imo_format")),
        sa.CheckConstraint(
            "length_m > 0 AND beam_m > 0 AND draft_m > 0",
            name=op.f("ck_vessels_positive_dimensions"),
        ),
        sa.CheckConstraint("gross_tonnage >= 0", name=op.f("ck_vessels_non_negative_tonnage")),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"], name=op.f("fk_vessels_company_id_companies")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vessels")),
        sa.UniqueConstraint("imo", name=op.f("uq_vessels_imo")),
    )
    op.create_index(op.f("ix_vessels_company_id"), "vessels", ["company_id"])

    op.create_table(
        "bookings",
        uuid_pk(),
        sa.Column("vessel_id", sa.Uuid(), nullable=False),
        sa.Column("slot_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_id", sa.Uuid(), nullable=False),
        sa.Column("status", booking_status, nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        created_at(),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["requested_by_id"], ["users.id"], name=op.f("fk_bookings_requested_by_id_users")
        ),
        sa.ForeignKeyConstraint(["slot_id"], ["slots.id"], name=op.f("fk_bookings_slot_id_slots")),
        sa.ForeignKeyConstraint(
            ["vessel_id"], ["vessels.id"], name=op.f("fk_bookings_vessel_id_vessels")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bookings")),
    )
    op.create_index(op.f("ix_bookings_vessel_id"), "bookings", ["vessel_id"])
    op.create_index("ix_bookings_slot_id_status", "bookings", ["slot_id", "status"])
    # Un créneau n'est attribué qu'à une seule demande.
    op.create_index(
        "uq_bookings_slot_accepted",
        "bookings",
        ["slot_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACCEPTED'"),
    )
    # Un navire n'a qu'une demande active (en attente ou acceptée) par créneau.
    op.create_index(
        "uq_bookings_vessel_slot_active",
        "bookings",
        ["vessel_id", "slot_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('PENDING', 'ACCEPTED')"),
    )

    op.create_table(
        "booking_events",
        uuid_pk(),
        sa.Column("booking_id", sa.Uuid(), nullable=False),
        sa.Column("from_status", booking_status, nullable=True),
        sa.Column("to_status", booking_status, nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        created_at(),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], name=op.f("fk_booking_events_actor_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["booking_id"],
            ["bookings.id"],
            name=op.f("fk_booking_events_booking_id_bookings"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_booking_events")),
    )
    op.create_index(op.f("ix_booking_events_booking_id"), "booking_events", ["booking_id"])

    op.create_table(
        "booking_services",
        sa.Column("booking_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["booking_id"],
            ["bookings.id"],
            name=op.f("fk_booking_services_booking_id_bookings"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["service_id"], ["services.id"], name=op.f("fk_booking_services_service_id_services")
        ),
        sa.PrimaryKeyConstraint("booking_id", "service_id", name=op.f("pk_booking_services")),
    )


def downgrade() -> None:
    # Supprimer une table supprime aussi ses index et contraintes.
    for table in (
        "booking_services",
        "booking_events",
        "bookings",
        "vessels",
        "slots",
        "services",
        "docks",
        "shipyards",
        "users",
        "ports",
        "companies",
    ):
        op.drop_table(table)
    bind = op.get_bind()
    for enum in reversed(ENUMS):
        enum.drop(bind, checkfirst=True)
    op.execute("DROP EXTENSION IF EXISTS btree_gist")
