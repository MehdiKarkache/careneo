# Carénéo

Plateforme de réservation de créneaux de carénage : un armateur (ferry, porte-conteneurs…) trouve
un poste de chantier naval compatible avec son navire et envoie une demande, que le chantier accepte
ou refuse. Un administrateur suit l'activité.

> Prototype réalisé pour l'exercice technique PUREGLIDE (groupe GREENOV-ITES).

**Présentation de l'architecture et des choix techniques (1 page) : [docs/architecture.pdf](docs/architecture.pdf)**

| Conception | |
| --- | --- |
| [Diagramme de classes](docs/diagramme-de-classes.png) | modèle du domaine, implémenté tel quel |
| [Contrat OpenAPI 3.1](docs/openapi.yaml) | 21 opérations ; les types du front en sont générés et un test vérifie que l'API s'y conforme |

## Lancer la démo

Prérequis : Docker.

```bash
docker compose up --build
```

Puis ouvrir http://localhost:8080 (documentation de l'API : http://localhost:8080/api/docs).

| Compte | Rôle | Entreprise |
| --- | --- | --- |
| `armateur@careneo.demo` | Armateur | Armement Hermine |
| `armateur2@careneo.demo` | Armateur | Lignes Mistral |
| `chantier@careneo.demo` | Chantier naval | Provence Réparation Navale (Marseille) |
| `chantier2@careneo.demo` | Chantier naval | Atlantique Carénage (Brest, Saint-Nazaire) |
| `admin@careneo.demo` | Administrateur | |

Mot de passe de tous les comptes : `demo1234`. Les données de démonstration sont datées à partir du
jour du lancement. Deux armateurs y convoitent le même créneau : accepter l'une des demandes refuse
automatiquement l'autre.

## Parcours

- **Armateur** : gère sa flotte (numéro IMO vérifié), recherche les créneaux d'un port compatibles
  avec les dimensions de son navire, envoie une demande avec des prestations, suit ou annule ses demandes.
- **Chantier** : ouvre des créneaux sur ses postes, gère ses services, accepte ou refuse les demandes
  avec un motif.
- **Administrateur** : statistiques par statut et par chantier, toutes les demandes.

## Stack

| Couche | Choix |
| --- | --- |
| Frontend | React 19, TypeScript, Vite, TanStack Query, Tailwind CSS ; client typé généré depuis le contrat |
| Backend | FastAPI (Python 3.12), Pydantic, session par cookie httpOnly, Argon2id |
| Données | PostgreSQL 17, SQLAlchemy 2 (async), Alembic ; invariants garantis par des contraintes |
| Exécution | Docker Compose : PostgreSQL, API, front servi par nginx (qui relaie `/api`) |

## Développement

```bash
docker compose up -d db                     # PostgreSQL seul

cd backend                                  # API sur http://localhost:8000
python -m venv .venv                        # Python 3.12
.venv\Scripts\activate                      # Windows (source .venv/bin/activate ailleurs)
pip install -r requirements-dev.txt
alembic upgrade head
python -m app.seed                          # --reset pour recréer les données de démo
uvicorn app.main:app --reload

cd frontend                                 # front sur http://localhost:5173
npm install
npm run dev
```

## Qualité

```bash
cd backend
python -m pytest        # 56 tests : domaine, API, requêtes concurrentes, conformité au contrat
ruff check . && ruff format --check .

cd frontend
npm run build           # vérification des types puis build de production
npm run api:types       # régénère les types après une modification du contrat
```

Les tests utilisent une base dédiée (`careneo_test`), créée et migrée automatiquement.

## Structure

```
backend/
  app/
    domain.py        règles pures : machine à états, clé IMO
    models.py        entités du diagramme et leurs méthodes (hybrides Python / SQL)
    usecases/        recherche et cycle de vie des réservations (transactions, verrous)
    routers/         routes HTTP, minces, une par tag du contrat
    schemas.py       schémas d'échange, nommés comme dans le contrat
  alembic/           migrations (contrainte d'exclusion, index uniques partiels)
  tests/
frontend/
  src/api/           client et types générés depuis le contrat
  src/pages/         écrans armateur, chantier et administrateur
docs/                diagramme, contrat OpenAPI, présentation de l'architecture (LaTeX et PDF)
```
