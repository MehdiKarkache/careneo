"""Contrôle d'accès aux ressources : une entreprise n'agit que sur ce qui lui appartient.

Ressource inexistante → 404 ; ressource d'une autre entreprise → 403 (cf. contrat).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.domain import Role
from app.errors import Forbidden, NotFound
from app.models import Dock, Shipyard, User, Vessel


async def get_owned_vessel(session: AsyncSession, vessel_id: uuid.UUID, user: User) -> Vessel:
    vessel = await session.get(Vessel, vessel_id)
    if vessel is None:
        raise NotFound("Navire introuvable")
    if vessel.company_id != user.company_id:
        raise Forbidden("Ce navire n'appartient pas à votre entreprise")
    return vessel


async def get_owned_shipyard(session: AsyncSession, shipyard_id: uuid.UUID, user: User) -> Shipyard:
    shipyard = await session.get(Shipyard, shipyard_id)
    if shipyard is None:
        raise NotFound("Chantier introuvable")
    if shipyard.company_id != user.company_id:
        raise Forbidden("Ce chantier n'appartient pas à votre entreprise")
    return shipyard


async def get_managed_dock(session: AsyncSession, dock_id: uuid.UUID, user: User) -> Dock:
    """Poste accessible au chantier qui le possède, ou à l'administrateur."""
    dock = await session.scalar(
        select(Dock).options(joinedload(Dock.shipyard)).where(Dock.id == dock_id)
    )
    if dock is None:
        raise NotFound("Poste introuvable")
    if not user.has_role(Role.ADMIN) and dock.shipyard.company_id != user.company_id:
        raise Forbidden("Ce poste n'appartient pas à votre entreprise")
    return dock
