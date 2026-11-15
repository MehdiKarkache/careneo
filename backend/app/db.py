"""Connexion à PostgreSQL : moteur asynchrone (asyncpg), sessions et validation des transactions."""

from collections.abc import AsyncIterator

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.errors import Conflict

engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Une session par requête HTTP. Les routes valident explicitement (commit) ;
    une session non validée est annulée à la fermeture."""
    async with SessionFactory() as session:
        yield session


# Invariants garantis par PostgreSQL (voir app.models) et message renvoyé quand une requête
# concurrente les viole malgré les vérifications applicatives.
CONSTRAINT_MESSAGES = {
    "uq_vessels_imo": "Un navire avec ce numéro IMO existe déjà",
    "ex_slots_no_overlap": "Ce créneau chevauche un créneau existant du poste",
    "uq_bookings_slot_accepted": "Ce créneau est déjà attribué à une autre demande",
    "uq_bookings_vessel_slot_active": "Une demande est déjà en cours pour ce navire sur ce créneau",
}


def violated_constraint(exc: IntegrityError) -> str | None:
    """Nom de la contrainte violée, exposé par asyncpg sous l'exception SQLAlchemy."""
    return getattr(exc.orig.__cause__, "constraint_name", None)


async def commit(session: AsyncSession) -> None:
    """Valide la transaction ; la violation d'un invariant connu devient un 409 explicite."""
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        message = CONSTRAINT_MESSAGES.get(violated_constraint(exc) or "")
        if message is None:
            raise
        raise Conflict(message) from exc
