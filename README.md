# Carénéo

Plateforme de réservation de créneaux de carénage : les armateurs (ferries, porte-conteneurs…)
trouvent un chantier naval compatible avec leur navire et lui envoient une demande de réservation,
que le chantier accepte ou refuse.

> Prototype réalisé dans le cadre de l'exercice technique PUREGLIDE (groupe GREENOV-ITES).

## Conception

- [Diagramme de classes](docs/diagramme-de-classes.png) : modèle du domaine
- [Contrat d'API OpenAPI 3.1](docs/openapi.yaml) : rôles requis, règles métier et codes d'erreur
  de chaque route

## Stack

| Couche          | Choix                                             |
| --------------- | ------------------------------------------------- |
| Frontend        | React + TypeScript (Vite)                         |
| Backend         | FastAPI (Python 3.12)                             |
| Base de données | PostgreSQL 17, SQLAlchemy 2 (async) + Alembic     |

Le guide de démarrage et la présentation de l'architecture arriveront avec le prototype.
