from typing import Literal

from pydantic import BaseModel
from sqlalchemy import text

from app.deps import SessionDep
from app.routers import api_router

router = api_router("Système")


class Health(BaseModel):
    status: Literal["ok"]


@router.get("/health", operation_id="health", summary="État de l'API et de la base de données")
async def health(session: SessionDep) -> Health:
    await session.execute(text("SELECT 1"))
    return Health(status="ok")
