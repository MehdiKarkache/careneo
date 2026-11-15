"""Requêtes simultanées : les verrous et les contraintes PostgreSQL garantissent qu'une seule
l'emporte, sans erreur 500 ni interblocage."""

import asyncio

import pytest
from conftest import OWNER, YARD, ApiFactory
from sqlalchemy import select

from app.db import SessionFactory, commit
from app.domain import SlotStatus
from app.errors import Conflict
from app.models import Slot


async def test_rival_requests_accepted_at_the_same_instant(api: ApiFactory) -> None:
    yard_a, yard_b = await api(YARD), await api(YARD)  # deux sessions du même chantier
    inbox = (await yard_a.get("/api/bookings", params={"status": "PENDING"})).json()
    rivals = [b for b in inbox if b["slot"]["id"] == inbox[0]["slot"]["id"]]
    assert len(rivals) == 2

    responses = await asyncio.gather(
        yard_a.post(f"/api/bookings/{rivals[0]['id']}/accept"),
        yard_b.post(f"/api/bookings/{rivals[1]['id']}/accept"),
    )
    assert sorted(r.status_code for r in responses) == [200, 409]
    statuses = [(await yard_a.get(f"/api/bookings/{b['id']}")).json()["status"] for b in rivals]
    assert sorted(statuses) == ["ACCEPTED", "REJECTED"]


async def test_identical_requests_sent_together_create_one_booking(api: ApiFactory) -> None:
    owner = await api(OWNER)
    vessel = next(
        v for v in (await owner.get("/api/vessels")).json() if v["name"] == "Hermine Ro-Ro"
    )
    port = next(p for p in (await owner.get("/api/ports")).json() if p["name"] == "Saint-Nazaire")
    params = {
        "portId": port["id"],
        "vesselId": vessel["id"],
        "from": "2000-01-01",
        "to": "2100-01-01",
    }
    slot = (await owner.get("/api/search", params=params)).json()[-1]
    body = {
        "vesselId": vessel["id"],
        "slotId": slot["slotId"],
        "serviceIds": [slot["services"][0]["id"]],
    }

    responses = await asyncio.gather(*(owner.post("/api/bookings", json=body) for _ in range(4)))
    assert sorted(r.status_code for r in responses) == [201, 409, 409, 409]


async def test_overlapping_slots_created_together_keep_only_one(api: ApiFactory) -> None:
    yard = await api(YARD)
    shipyard = (await yard.get("/api/shipyards")).json()[0]
    dock = (await yard.get(f"/api/shipyards/{shipyard['id']}")).json()["docks"][0]
    body = {"startDate": "2032-06-01", "endDate": "2032-06-10"}

    responses = await asyncio.gather(
        *(yard.post(f"/api/docks/{dock['id']}/slots", json=body) for _ in range(4))
    )
    assert sorted(r.status_code for r in responses) == [201, 409, 409, 409]


async def test_the_database_has_the_last_word_on_overlapping_slots() -> None:
    """Sans passer par la vérification applicative, la contrainte d'exclusion refuse le créneau
    et l'API la traduit en un 409 lisible."""
    async with SessionFactory() as session:
        existing = await session.scalar(select(Slot).where(Slot.status == SlotStatus.OPEN).limit(1))
        assert existing is not None
        session.add(
            Slot(
                dock_id=existing.dock_id, start_date=existing.start_date, end_date=existing.end_date
            )
        )
        with pytest.raises(Conflict, match="chevauche un créneau existant"):
            await commit(session)
