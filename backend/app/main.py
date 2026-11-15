"""Point d'entrée de l'API Carénéo.

Documentation interactive : http://localhost:8000/api/docs
Contrat de référence : docs/openapi.yaml (les tests vérifient que l'API s'y conforme).
"""

from fastapi import FastAPI

from app.errors import register_error_handlers
from app.routers import admin, auth, bookings, ports, search, shipyards, system, vessels


def create_app() -> FastAPI:
    app = FastAPI(
        title="Carénéo API",
        version="0.3.0",
        description="Réservation de créneaux de carénage auprès de chantiers navals.",
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url=None,
        swagger_ui_oauth2_redirect_url=None,
    )
    register_error_handlers(app)
    for module in (auth, ports, vessels, search, shipyards, bookings, admin, system):
        app.include_router(module.router)
    return app


app = create_app()
