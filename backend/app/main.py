"""Point d'entrée de l'API Carénéo.

Documentation interactive : http://localhost:8000/api/docs
Contrat de référence : docs/openapi.yaml (vérifié par les tests).
"""

from fastapi import FastAPI

from app.routers import system


def create_app() -> FastAPI:
    app = FastAPI(
        title="Carénéo API",
        version="0.3.0",
        description="Réservation de créneaux de carénage auprès de chantiers navals.",
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url=None,
    )
    app.include_router(system.router)
    return app


app = create_app()
