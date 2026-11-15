"""Schémas d'échange JSON, calqués sur le contrat (docs/openapi.yaml) et nommés comme lui.

Champs en snake_case côté Python, en camelCase dans le JSON. Les corps de requête refusent
les champs inconnus plutôt que de les ignorer silencieusement.
"""

import re
import uuid
from datetime import date
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationInfo,
    field_validator,
)
from pydantic.alias_generators import to_camel

from app.domain import CompanyType, DockType, Role, SlotStatus, VesselType, is_valid_imo


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
        from_attributes=True,
        allow_inf_nan=False,
    )


class InputModel(ApiModel):
    model_config = ConfigDict(extra="forbid")


# ---------- Types réutilisables ----------

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Meters = Annotated[float, Field(gt=0)]


def _normalize_imo(value: object) -> object:
    # Accepte aussi la forme usuelle « IMO 9421001 ».
    return value.upper().removeprefix("IMO").strip() if isinstance(value, str) else value


def _check_imo(value: str) -> str:
    if not re.fullmatch(r"[0-9]{7}", value):
        raise ValueError("Le numéro IMO doit comporter exactement 7 chiffres")
    if not is_valid_imo(value):
        raise ValueError("Numéro IMO invalide : la clé de contrôle (7e chiffre) ne correspond pas")
    return value


Imo = Annotated[
    str,
    BeforeValidator(_normalize_imo),
    AfterValidator(_check_imo),
    Field(json_schema_extra={"pattern": "^[0-9]{7}$"}, examples=["9421001"]),
]


# ---------- Authentification ----------


class LoginInput(InputModel):
    email: Annotated[
        str, StringConstraints(strip_whitespace=True, to_lower=True, min_length=3, max_length=254)
    ]
    password: Annotated[str, Field(min_length=1, max_length=256)]


class CompanySummary(ApiModel):
    id: uuid.UUID
    name: str
    type: CompanyType


class Me(ApiModel):
    id: uuid.UUID
    email: str
    name: str
    role: Role
    company: CompanySummary | None = None


# ---------- Référentiel ----------


class Port(ApiModel):
    id: uuid.UUID
    name: str
    country: str
    unlocode: str


# ---------- Navires ----------


class VesselInput(InputModel):
    name: Name
    imo: Imo
    type: VesselType
    length_m: Annotated[Meters, Field(description="Longueur hors-tout en mètres")]
    beam_m: Annotated[Meters, Field(description="Largeur en mètres")]
    draft_m: Annotated[Meters, Field(description="Tirant d'eau en mètres")]
    gross_tonnage: Annotated[int, Field(ge=0, description="Jauge brute")] | None = None


class VesselUpdate(InputModel):
    """Seuls les champs envoyés sont modifiés. L'IMO, identifiant du navire, ne l'est pas."""

    name: Name | None = None
    type: VesselType | None = None
    length_m: Meters | None = None
    beam_m: Meters | None = None
    draft_m: Meters | None = None
    gross_tonnage: Annotated[int, Field(ge=0)] | None = None  # null efface la valeur

    @field_validator("name", "type", "length_m", "beam_m", "draft_m", mode="before")
    @classmethod
    def _not_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("Ne peut pas être vide")
        return value


class Vessel(ApiModel):
    id: uuid.UUID
    company_id: uuid.UUID
    name: str
    imo: str
    type: VesselType
    length_m: float
    beam_m: float
    draft_m: float
    gross_tonnage: int | None = None


class VesselSummary(ApiModel):
    id: uuid.UUID
    name: str
    imo: str
    type: VesselType


# ---------- Chantiers ----------


class Dock(ApiModel):
    id: uuid.UUID
    name: str
    type: DockType
    max_length_m: float
    max_beam_m: float
    max_draft_m: float


class ServiceInput(InputModel):
    name: Name
    category: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
    indicative_price: (
        Annotated[int, Field(ge=0, description="Prix indicatif en euros HT")] | None
    ) = None


class Service(ApiModel):
    id: uuid.UUID
    name: str
    category: str
    indicative_price: int | None = None


class ShipyardSummary(ApiModel):
    id: uuid.UUID
    name: str
    port: Port


class ShipyardDetail(ShipyardSummary):
    description: str | None = None
    docks: list[Dock]
    services: list[Service]


# ---------- Créneaux ----------


class SlotInput(InputModel):
    start_date: date
    end_date: date

    @field_validator("end_date")
    @classmethod
    def _end_not_before_start(cls, end_date: date, info: ValidationInfo) -> date:
        start_date = info.data.get("start_date")
        if start_date is not None and end_date < start_date:
            raise ValueError("La date de fin doit être postérieure ou égale à la date de début")
        return end_date


class Slot(ApiModel):
    id: uuid.UUID
    dock_id: uuid.UUID
    start_date: date
    end_date: date
    status: SlotStatus
