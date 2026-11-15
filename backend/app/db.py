"""Connexion à PostgreSQL : moteur asynchrone (asyncpg) et fabrique de sessions."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Une session par requête HTTP. Les routes valident explicitement (commit) ;
    une session non validée est annulée à la fermeture."""
    async with SessionFactory() as session:
        yield session
