"""Données de démonstration, datées à partir d'aujourd'hui pour que la démo reste valable.

    python -m app.seed           # remplit une base vide (sans effet si elle contient des données)
    python -m app.seed --reset   # vide la base puis la remplit

Comptes (mot de passe : demo1234) :
    armateur@careneo.demo    OWNER  Armement Hermine
    armateur2@careneo.demo   OWNER  Lignes Mistral
    chantier@careneo.demo    YARD   Provence Réparation Navale (Marseille)
    chantier2@careneo.demo   YARD   Atlantique Carénage (Brest, Saint-Nazaire)
    vieuxport@careneo.demo   YARD   Chantier du Vieux-Port (Marseille)
    admin@careneo.demo       ADMIN

Les réservations de démo passent par les méthodes métier (Booking.request, accept, reject,
cancel) : elles respectent donc la machine à états et produisent leur historique.
"""

import argparse
import asyncio
from datetime import date, timedelta

from sqlalchemy import func, select, text

from app.db import SessionFactory, engine
from app.domain import CompanyType, DockType, Role, SlotStatus, VesselType, today, utcnow
from app.models import Base, Booking, Company, Dock, Port, Service, Shipyard, Slot, User, Vessel
from app.security import hash_password

DEMO_PASSWORD = "demo1234"


def slot_series(dock: Dock, first_start: date, count: int = 8, days: int = 12) -> list[Slot]:
    """Créneaux réguliers de `days` jours sur un poste, un départ toutes les trois semaines."""
    return [
        Slot(
            dock=dock,
            start_date=first_start + timedelta(weeks=3 * i),
            end_date=first_start + timedelta(weeks=3 * i, days=days - 1),
        )
        for i in range(count)
    ]


def pick(services: list[Service], *categories: str) -> list[Service]:
    return [service for service in services if service.category in categories]


def backdate(booking: Booking, *days_ago: float) -> None:
    """Antidate une demande et ses événements (un délai par événement, du plus ancien au plus
    récent), pour que l'historique de démo paraisse réaliste."""
    now = utcnow()
    for event, ago in zip(booking.events, days_ago, strict=True):
        event.created_at = now - timedelta(days=ago)
    booking.created_at = booking.events[0].created_at
    if booking.decided_at is not None:
        booking.decided_at = booking.events[-1].created_at


def build_demo_data() -> list[object]:
    start = today()
    password_hash = hash_password(DEMO_PASSWORD)

    # ---------- Ports ----------
    marseille = Port(name="Marseille", country="FR", unlocode="FRMRS")
    brest = Port(name="Brest", country="FR", unlocode="FRBES")
    saint_nazaire = Port(name="Saint-Nazaire", country="FR", unlocode="FRSNR")
    le_havre = Port(name="Le Havre", country="FR", unlocode="FRLEH")
    dunkerque = Port(name="Dunkerque", country="FR", unlocode="FRDKK")

    # ---------- Entreprises et utilisateurs ----------
    hermine = Company(name="Armement Hermine", type=CompanyType.SHIPOWNER)
    mistral = Company(name="Lignes Mistral", type=CompanyType.SHIPOWNER)
    prn = Company(name="Provence Réparation Navale", type=CompanyType.SHIPYARD)
    atlantique = Company(name="Atlantique Carénage", type=CompanyType.SHIPYARD)
    vieux_port = Company(name="Chantier du Vieux-Port", type=CompanyType.SHIPYARD)

    def user(email: str, name: str, role: Role, company: Company | None = None) -> User:
        return User(email=email, name=name, role=role, company=company, password_hash=password_hash)

    owner = user("armateur@careneo.demo", "Camille Durand", Role.OWNER, hermine)
    owner2 = user("armateur2@careneo.demo", "Hugo Lefèvre", Role.OWNER, mistral)
    yard = user("chantier@careneo.demo", "Nadia Rossi", Role.YARD, prn)
    yard2 = user("chantier2@careneo.demo", "Yann Le Bihan", Role.YARD, atlantique)
    yard3 = user("vieuxport@careneo.demo", "Marc Giraud", Role.YARD, vieux_port)
    admin = user("admin@careneo.demo", "Équipe Carénéo", Role.ADMIN)

    # ---------- Chantiers, postes (L × l × tirant d'eau max, en m) et services ----------
    def dock(name: str, kind: DockType, length: float, beam: float, draft: float) -> Dock:
        return Dock(name=name, type=kind, max_length_m=length, max_beam_m=beam, max_draft_m=draft)

    def service(name: str, category: str, price: int) -> Service:
        return Service(name=name, category=category, indicative_price=price)

    forme_1 = dock("Forme 1", DockType.DRY_DOCK, 320, 50, 13)
    forme_2 = dock("Forme 2", DockType.DRY_DOCK, 210, 32, 9)
    dock_flottant = dock("Dock flottant", DockType.FLOATING_DOCK, 180, 30, 7.5)
    prn_services = [
        service("Hydronettoyage haute pression de la coque", "HULL_CLEANING", 4_800),
        service("Application d'antifouling", "ANTIFOULING", 21_000),
        service("Remplacement des anodes sacrificielles", "ANODES", 3_500),
        service("Polissage d'hélice", "PROPELLER", 4_200),
        service("Inspection de coque et mesures d'épaisseur", "INSPECTION", 2_900),
    ]
    prn_marseille = Shipyard(
        name="Provence Réparation Navale",
        description="Carénage et réparation de navires jusqu'à 320 m, bassins Est du port.",
        port=marseille,
        company=prn,
        docks=[forme_1, forme_2, dock_flottant],
        services=prn_services,
    )

    elevateur = dock("Élévateur à navires", DockType.SHIPLIFT, 95, 18, 5)
    vieux_port_yard = Shipyard(
        name="Chantier du Vieux-Port",
        description="Unités de moins de 95 m : vedettes, remorqueurs, navires de servitude.",
        port=marseille,
        company=vieux_port,
        docks=[elevateur],
        services=[
            service("Carénage complet petite unité", "HULL_CLEANING", 2_400),
            service("Application d'antifouling", "ANTIFOULING", 6_500),
        ],
    )

    forme_a = dock("Forme A", DockType.DRY_DOCK, 300, 45, 11)
    forme_b = dock("Forme B", DockType.DRY_DOCK, 225, 34, 9)
    brest_services = [
        service("Hydronettoyage haute pression de la coque", "HULL_CLEANING", 4_500),
        service("Application d'antifouling", "ANTIFOULING", 19_500),
        service("Révision des vannes de coque", "VALVES", 5_600),
        service("Inspection de coque et mesures d'épaisseur", "INSPECTION", 2_700),
    ]
    brest_yard = Shipyard(
        name="Atlantique Carénage Brest",
        description="Deux formes de radoub pour ferries, rouliers et navires de charge.",
        port=brest,
        company=atlantique,
        docks=[forme_a, forme_b],
        services=brest_services,
    )

    dock_nord = dock("Dock flottant Nord", DockType.FLOATING_DOCK, 240, 38, 9)
    nazaire_yard = Shipyard(
        name="Atlantique Carénage Saint-Nazaire",
        description="Dock flottant pour navires jusqu'à 240 m, à l'entrée de l'estuaire.",
        port=saint_nazaire,
        company=atlantique,
        docks=[dock_nord],
        services=[
            service("Hydronettoyage haute pression de la coque", "HULL_CLEANING", 4_600),
            service("Application d'antifouling", "ANTIFOULING", 20_500),
            service("Remplacement des anodes sacrificielles", "ANODES", 3_300),
        ],
    )

    # Créneaux de 12 jours toutes les trois semaines, décalés d'un poste à l'autre.
    docks = [forme_1, forme_2, dock_flottant, elevateur, forme_a, forme_b, dock_nord]
    schedule = {d: slot_series(d, start + timedelta(days=10 + 4 * k)) for k, d in enumerate(docks)}
    schedule[forme_a][5].status = SlotStatus.CLOSED  # arrêt technique du poste

    # ---------- Navires ----------
    express = Vessel(
        name="Hermine Express", imo="9421001", type=VesselType.FERRY,
        length_m=186, beam_m=28.5, draft_m=6.8, gross_tonnage=32_000, company=hermine,
    )  # fmt: skip
    cargo = Vessel(
        name="Hermine Cargo", imo="9512343", type=VesselType.CONTAINER_SHIP,
        length_m=294, beam_m=32.3, draft_m=12.5, gross_tonnage=52_000, company=hermine,
    )  # fmt: skip
    roro = Vessel(
        name="Hermine Ro-Ro", imo="9706542", type=VesselType.RO_RO,
        length_m=142, beam_m=23, draft_m=5.9, gross_tonnage=18_500, company=hermine,
    )  # fmt: skip
    star = Vessel(
        name="Mistral Star", imo="9334014", type=VesselType.FERRY,
        length_m=175, beam_m=27, draft_m=6.5, gross_tonnage=29_000, company=mistral,
    )  # fmt: skip

    # ---------- Réservations ----------
    # Deux armateurs demandent le même créneau : le chantier n'en acceptera qu'une.
    pending_1 = Booking.request(
        vessel=express,
        slot=schedule[forme_1][1],
        services=pick(prn_services, "ANTIFOULING", "ANODES"),
        by=owner,
        message="Carénage annuel. Arrivée prévue la veille au soir.",
    )
    backdate(pending_1, 2)
    pending_2 = Booking.request(
        vessel=star,
        slot=schedule[forme_1][1],
        services=pick(prn_services, "HULL_CLEANING", "ANTIFOULING"),
        by=owner2,
        message="Arrêt technique programmé, dates flexibles à deux jours près.",
    )
    backdate(pending_2, 1)

    accepted = Booking.request(
        vessel=roro,
        slot=schedule[forme_b][0],
        services=pick(brest_services, "HULL_CLEANING", "VALVES"),
        by=owner,
    )
    accepted.accept(by=yard2)
    backdate(accepted, 9, 7)

    rejected = Booking.request(
        vessel=express,
        slot=schedule[forme_a][2],
        services=pick(brest_services, "ANTIFOULING"),
        by=owner,
    )
    rejected.reject(by=yard2, reason="Forme A immobilisée pour la maintenance du bateau-porte")
    backdate(rejected, 12, 10)

    cancelled = Booking.request(
        vessel=star,
        slot=schedule[forme_2][3],
        services=pick(prn_services, "INSPECTION"),
        by=owner2,
    )
    cancelled.cancel(by=owner2)
    backdate(cancelled, 6, 5)

    return [
        *(marseille, brest, saint_nazaire, le_havre, dunkerque),
        *(owner, owner2, yard, yard2, yard3, admin),
        *(prn_marseille, vieux_port_yard, brest_yard, nazaire_yard),
        *(slot for series in schedule.values() for slot in series),
        *(express, cargo, roro, star),
        *(pending_1, pending_2, accepted, rejected, cancelled),
    ]


async def seed(reset: bool) -> None:
    async with SessionFactory() as session:
        if reset:
            tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
            await session.execute(text(f"TRUNCATE {tables} CASCADE"))
        elif await session.scalar(select(func.count()).select_from(User)):
            print("La base contient déjà des données : rien à faire (--reset pour la recréer).")
            return
        session.add_all(build_demo_data())
        await session.commit()
    print(f"Données de démonstration créées. Mot de passe des comptes : {DEMO_PASSWORD}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Charge les données de démonstration.")
    parser.add_argument("--reset", action="store_true", help="vide la base avant de la remplir")
    try:
        await seed(parser.parse_args().reset)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
