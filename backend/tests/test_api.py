"""Parcours HTTP complets sur les données de démonstration."""

from datetime import timedelta

import pytest
from conftest import ADMIN, OWNER, OWNER2, YARD, YARD2, ApiFactory

from app.domain import today


async def test_session_cookie_is_httponly_and_logout_clears_it(api: ApiFactory) -> None:
    client = await api()
    login = await client.post("/api/auth/login", json={"email": OWNER, "password": "demo1234"})
    assert login.status_code == 200 and login.json()["company"]["name"] == "Armement Hermine"
    cookie = login.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    assert (await client.get("/api/auth/me")).status_code == 200
    assert (await client.post("/api/auth/logout")).status_code == 204
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_unknown_email_and_wrong_password_get_the_same_answer(api: ApiFactory) -> None:
    client = await api()
    wrong = await client.post("/api/auth/login", json={"email": OWNER, "password": "x"})
    unknown = await client.post("/api/auth/login", json={"email": "nobody@x.fr", "password": "x"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


async def test_validation_errors_use_the_contract_format_in_french(api: ApiFactory) -> None:
    owner = await api(OWNER)
    response = await owner.post(
        "/api/vessels",
        json={"name": " ", "imo": "9421002", "type": "YACHT", "lengthM": 0, "beamM": 20,
              "draftM": 6, "color": "rouge"},
    )  # fmt: skip
    assert response.status_code == 400
    assert response.json()["error"] == {
        "code": "VALIDATION_ERROR",
        "message": "Données invalides",
        "details": {
            "name": "Ne peut pas être vide",
            "imo": "Numéro IMO invalide : la clé de contrôle (7e chiffre) ne correspond pas",
            "type": "Valeur non autorisée (attendu : 'FERRY', 'CONTAINER_SHIP', 'TANKER', "
            "'RO_RO' ou 'OTHER')",
            "lengthM": "Doit être strictement supérieur à 0",
            "color": "Champ non autorisé",
        },
    }


@pytest.mark.parametrize(
    ("email", "method", "url", "status"),
    [
        (None, "GET", "/api/ports", 401),
        (YARD, "GET", "/api/vessels", 403),
        (YARD, "GET", "/api/search", 403),
        (OWNER, "GET", "/api/admin/stats", 403),
        (ADMIN, "POST", "/api/bookings", 403),
    ],
)
async def test_role_guards(
    api: ApiFactory, email: str | None, method: str, url: str, status: int
) -> None:
    client = await api(email)
    assert (await client.request(method, url, json={})).status_code == status


async def test_companies_only_act_on_their_own_resources(api: ApiFactory) -> None:
    owner, owner2, yard = await api(OWNER), await api(OWNER2), await api(YARD)
    star = (await owner2.get("/api/vessels")).json()[0]
    assert (await owner.patch(f"/api/vessels/{star['id']}", json={"name": "X"})).status_code == 403
    assert (
        await owner.patch(f"/api/vessels/{'0' * 8}-0000-0000-0000-{'0' * 12}", json={"name": "X"})
    ).status_code == 404

    brest = (await owner.get("/api/shipyards")).json()
    other_yard = next(s for s in brest if s["name"] == "Atlantique Carénage Brest")
    other_dock = (await owner.get(f"/api/shipyards/{other_yard['id']}")).json()["docks"][0]
    response = await yard.post(
        f"/api/docks/{other_dock['id']}/slots",
        json={"startDate": "2031-01-01", "endDate": "2031-01-05"},
    )
    assert response.status_code == 403
    assert [s["name"] for s in (await yard.get("/api/shipyards")).json()] == [
        "Provence Réparation Navale"
    ]


async def test_search_applies_the_dock_compatibility_rule(api: ApiFactory) -> None:
    owner = await api(OWNER)
    port = next(p for p in (await owner.get("/api/ports")).json() if p["name"] == "Marseille")
    fleet = {v["name"]: v["id"] for v in (await owner.get("/api/vessels")).json()}
    window = {"portId": port["id"], "from": str(today()), "to": str(today() + timedelta(days=60))}

    ferry = (
        await owner.get("/api/search", params={**window, "vesselId": fleet["Hermine Express"]})
    ).json()
    cargo = (
        await owner.get("/api/search", params={**window, "vesselId": fleet["Hermine Cargo"]})
    ).json()

    # Le dock flottant (180 m) et l'élévateur (95 m) sont trop petits pour le ferry de 186 m ;
    # seul le poste Forme 1 accepte les 12,5 m de tirant d'eau du porte-conteneurs.
    assert {r["dock"]["name"] for r in ferry} == {"Forme 1", "Forme 2"}
    assert {r["dock"]["name"] for r in cargo} == {"Forme 1"}
    assert [r["startDate"] for r in ferry] == sorted(r["startDate"] for r in ferry)
    assert sum("existingBookingId" in r for r in ferry) == 1

    reversed_window = {
        **window,
        "from": window["to"],
        "to": window["from"],
        "vesselId": fleet["Hermine Cargo"],
    }
    response = await owner.get("/api/search", params=reversed_window)
    assert response.json()["error"]["details"] == {
        "to": "La date de fin doit suivre la date de début"
    }


async def test_booking_request_rules(api: ApiFactory) -> None:
    owner = await api(OWNER)
    port = next(p for p in (await owner.get("/api/ports")).json() if p["name"] == "Marseille")
    fleet = {v["name"]: v["id"] for v in (await owner.get("/api/vessels")).json()}
    window = {"portId": port["id"], "from": str(today()), "to": str(today() + timedelta(days=60))}
    results = (
        await owner.get("/api/search", params={**window, "vesselId": fleet["Hermine Express"]})
    ).json()
    forme_2 = next(r for r in results if r["dock"]["name"] == "Forme 2")
    rival_slot = next(r for r in results if "existingBookingId" in r)  # convoité par deux armateurs

    def request(vessel: str, slot: dict, services: list[str] | None = None) -> dict:
        return {"vesselId": fleet[vessel], "slotId": slot["slotId"],
                "serviceIds": services or [slot["services"][0]["id"]]}  # fmt: skip

    created = await owner.post("/api/bookings", json=request("Hermine Express", forme_2))
    assert created.status_code == 201 and created.json()["status"] == "PENDING"

    duplicate = await owner.post("/api/bookings", json=request("Hermine Express", forme_2))
    too_big = await owner.post("/api/bookings", json=request("Hermine Cargo", forme_2))
    overlapping = await owner.post("/api/bookings", json=request("Hermine Ro-Ro", rival_slot))
    foreign_service = await owner.post(
        "/api/bookings", json=request("Hermine Ro-Ro", forme_2, [str(fleet["Hermine Cargo"])])
    )
    assert (duplicate.status_code, too_big.status_code, overlapping.status_code) == (409, 409, 409)
    assert "déjà en cours" in duplicate.json()["error"]["message"]
    assert "dépasse les dimensions" in too_big.json()["error"]["message"]
    assert "carénage confirmé" in overlapping.json()["error"]["message"]
    assert (
        foreign_service.status_code == 400
        and "serviceIds" in foreign_service.json()["error"]["details"]
    )


async def test_accepting_a_request_books_the_slot_and_rejects_the_rivals(api: ApiFactory) -> None:
    yard, yard2, owner2 = await api(YARD), await api(YARD2), await api(OWNER2)
    inbox = (await yard.get("/api/bookings", params={"status": "PENDING"})).json()
    chosen = next(b for b in inbox if b["vessel"]["name"] == "Hermine Express")
    rival = next(b for b in inbox if b["vessel"]["name"] == "Mistral Star")
    assert chosen["slot"]["id"] == rival["slot"]["id"]

    assert (await yard2.post(f"/api/bookings/{chosen['id']}/accept")).status_code == 403
    accepted = await yard.post(f"/api/bookings/{chosen['id']}/accept")
    assert accepted.status_code == 200 and accepted.json()["status"] == "ACCEPTED"

    rejected = (await owner2.get(f"/api/bookings/{rival['id']}")).json()
    assert rejected["status"] == "REJECTED"
    assert rejected["rejectionReason"] == "Créneau attribué à une autre demande"
    assert [(e.get("fromStatus"), e["toStatus"], e["actorName"]) for e in rejected["events"]] == [
        (None, "PENDING", "Hugo Lefèvre"),
        ("PENDING", "REJECTED", "Nadia Rossi"),
    ]
    slots = (await yard.get(f"/api/docks/{chosen['slot']['dock']['id']}/slots")).json()
    assert next(s for s in slots if s["id"] == chosen["slot"]["id"])["status"] == "BOOKED"

    again = await yard.post(f"/api/bookings/{rival['id']}/accept")
    assert again.status_code == 409
    assert again.json()["error"]["message"] == "Demande déjà traitée (statut : refusée)"


async def test_rejection_keeps_the_slot_open_and_owners_cancel_their_requests(
    api: ApiFactory,
) -> None:
    yard, owner, owner2 = await api(YARD), await api(OWNER), await api(OWNER2)
    inbox = (await yard.get("/api/bookings", params={"status": "PENDING"})).json()
    mine = next(b for b in inbox if b["vessel"]["name"] == "Hermine Express")
    theirs = next(b for b in inbox if b["vessel"]["name"] == "Mistral Star")

    short = await yard.post(f"/api/bookings/{mine['id']}/reject", json={"reason": "no"})
    assert short.status_code == 400 and "reason" in short.json()["error"]["details"]
    rejected = await yard.post(
        f"/api/bookings/{mine['id']}/reject", json={"reason": "Forme en maintenance"}
    )
    assert rejected.json()["status"] == "REJECTED"
    slots = (await yard.get(f"/api/docks/{mine['slot']['dock']['id']}/slots")).json()
    assert next(s for s in slots if s["id"] == mine["slot"]["id"])["status"] == "OPEN"

    assert (await owner.post(f"/api/bookings/{theirs['id']}/cancel")).status_code == 403
    cancelled = await owner2.post(f"/api/bookings/{theirs['id']}/cancel")
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "CANCELLED"
    assert (await owner2.post(f"/api/bookings/{theirs['id']}/cancel")).status_code == 409


async def test_each_role_sees_its_own_bookings_and_admin_sees_stats(api: ApiFactory) -> None:
    owner, owner2, yard, admin = (
        await api(OWNER),
        await api(OWNER2),
        await api(YARD),
        await api(ADMIN),
    )
    assert len((await owner.get("/api/bookings")).json()) == 3
    assert len((await owner2.get("/api/bookings")).json()) == 2
    assert len((await yard.get("/api/bookings")).json()) == 3
    everything = (await admin.get("/api/bookings")).json()
    assert len(everything) == 5

    stats = (await admin.get("/api/admin/stats")).json()
    assert stats["byStatus"] == {"PENDING": 2, "ACCEPTED": 1, "REJECTED": 1, "CANCELLED": 1,
                                 "EXPIRED": 0, "COMPLETED": 0}  # fmt: skip
    assert sum(s["total"] for s in stats["byShipyard"]) == 5


async def test_slot_creation_rules(api: ApiFactory) -> None:
    yard = await api(YARD)
    shipyard = (await yard.get("/api/shipyards")).json()[0]
    dock = (await yard.get(f"/api/shipyards/{shipyard['id']}")).json()["docks"][0]
    url = f"/api/docks/{dock['id']}/slots"
    existing = (await yard.get(url)).json()[0]

    overlap = await yard.post(
        url, json={"startDate": existing["startDate"], "endDate": existing["endDate"]}
    )
    reversed_dates = await yard.post(url, json={"startDate": "2031-01-10", "endDate": "2031-01-01"})
    starts_today = await yard.post(url, json={"startDate": str(today()), "endDate": str(today())})
    created = await yard.post(url, json={"startDate": "2031-01-01", "endDate": "2031-01-12"})

    assert overlap.status_code == 409
    assert (
        reversed_dates.status_code == 400 and "endDate" in reversed_dates.json()["error"]["details"]
    )
    assert (
        starts_today.status_code == 400 and "startDate" in starts_today.json()["error"]["details"]
    )
    assert created.status_code == 201 and created.json()["status"] == "OPEN"
