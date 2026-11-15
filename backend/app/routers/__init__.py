"""Routes HTTP, regroupées comme les tags du contrat (docs/openapi.yaml)."""

from typing import Any

from fastapi import APIRouter
from fastapi.routing import APIRoute


class ContractRoute(APIRoute):
    """Omet des réponses les champs optionnels sans valeur : le contrat les déclare optionnels,
    pas nullables (champ absent plutôt que `null`)."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs["response_model_exclude_none"] = True
        super().__init__(*args, **kwargs)


def api_router(tag: str) -> APIRouter:
    return APIRouter(prefix="/api", tags=[tag], route_class=ContractRoute)
