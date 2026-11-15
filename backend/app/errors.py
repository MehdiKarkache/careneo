"""Erreurs de l'API au format du contrat : {"error": {"code", "message", "details"?}}.

- ApiError et ses sous-classes : erreurs levées volontairement par les routes ;
- DomainError (app.domain) : règle métier violée, traduite en 409 ;
- erreurs de validation Pydantic : 400, avec un message en français par champ.
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.domain import DomainError


class ApiError(Exception):
    status_code = 500
    code = "INTERNAL_ERROR"
    default_message = "Erreur interne"

    def __init__(self, message: str | None = None, details: dict[str, str] | None = None):
        self.message = message or self.default_message
        self.details = details
        super().__init__(self.message)


class ValidationFailed(ApiError):
    status_code = 400
    code = "VALIDATION_ERROR"
    default_message = "Données invalides"


class Unauthenticated(ApiError):
    status_code = 401
    code = "UNAUTHENTICATED"
    default_message = "Connexion requise"


class Forbidden(ApiError):
    status_code = 403
    code = "FORBIDDEN"
    default_message = "Accès refusé"


class NotFound(ApiError):
    status_code = 404
    code = "NOT_FOUND"
    default_message = "Ressource introuvable"


class Conflict(ApiError):
    status_code = 409
    code = "CONFLICT"
    default_message = "Conflit avec l'état actuel de la ressource"


def error_response(
    status_code: int, code: str, message: str, details: dict[str, Any] | None = None
) -> JSONResponse:
    error: dict[str, Any] = {"code": code, "message": message}
    if details:
        error["details"] = details
    return JSONResponse(status_code=status_code, content={"error": error})


# ---------- Erreurs de validation ----------

# Messages en français des erreurs Pydantic courantes ; {…} est rempli par le contexte de l'erreur.
VALIDATION_MESSAGES = {
    "missing": "Champ obligatoire",
    "extra_forbidden": "Champ non autorisé",
    "string_type": "Texte attendu",
    "string_too_short": "Trop court (minimum {min_length} caractère(s))",
    "string_too_long": "Trop long (maximum {max_length} caractères)",
    "string_pattern_mismatch": "Format invalide",
    "int_type": "Nombre entier attendu",
    "int_parsing": "Nombre entier attendu",
    "int_from_float": "Nombre entier attendu",
    "float_type": "Nombre attendu",
    "float_parsing": "Nombre attendu",
    "finite_number": "Nombre fini attendu",
    "greater_than": "Doit être strictement supérieur à {gt}",
    "greater_than_equal": "Doit être supérieur ou égal à {ge}",
    "date_type": "Date attendue (AAAA-MM-JJ)",
    "date_parsing": "Date invalide (AAAA-MM-JJ)",
    "date_from_datetime_parsing": "Date invalide (AAAA-MM-JJ)",
    "date_from_datetime_inexact": "Date sans heure attendue (AAAA-MM-JJ)",
    "uuid_type": "Identifiant invalide",
    "uuid_parsing": "Identifiant invalide",
    "enum": "Valeur non autorisée (attendu : {expected})",
    "list_type": "Liste attendue",
    "too_short": "Au moins {min_length} élément(s) attendu(s)",
    "too_long": "Au plus {max_length} élément(s)",
    "model_attributes_type": "Objet JSON attendu",
    "dict_type": "Objet JSON attendu",
    "json_invalid": "JSON invalide",
}

_LOCATIONS = {"body", "query", "path", "cookie", "header"}


class _Context(dict[str, Any]):
    """Contexte d'erreur tolérant : une clé absente n'empêche pas de former le message."""

    def __missing__(self, key: str) -> str:
        return "?"


def _readable(value: Any) -> Any:
    if isinstance(value, float) and value.is_integer():
        return int(value)  # « supérieur à 0 » plutôt que « supérieur à 0.0 »
    if isinstance(value, str):
        return value.replace(" or ", " ou ")  # liste de valeurs attendues d'une énumération
    return value


def validation_details(errors: list[dict[str, Any]]) -> dict[str, str]:
    """Un message par champ en erreur, ex. {"lengthM": "Doit être strictement supérieur à 0"}."""
    details: dict[str, str] = {}
    for error in errors:
        kind = error["type"]
        path = [str(part) for part in error["loc"] if part not in _LOCATIONS]
        field = "body" if kind == "json_invalid" or not path else ".".join(path)
        context = _Context(
            {key: _readable(value) for key, value in (error.get("ctx") or {}).items()}
        )
        if kind == "value_error" and "error" in context:
            message = str(context["error"])  # message d'un validateur maison, déjà en français
        elif kind == "string_too_short" and context.get("min_length") == 1:
            message = "Ne peut pas être vide"
        elif kind in VALIDATION_MESSAGES:
            message = VALIDATION_MESSAGES[kind].format_map(context)
        else:
            message = error["msg"]
        details.setdefault(field, message)
    return details


# ---------- Enregistrement des gestionnaires ----------

# Erreurs produites par le framework lui-même (route inconnue, méthode non autorisée…)
_FRAMEWORK_ERRORS = {
    401: ("UNAUTHENTICATED", "Connexion requise"),
    403: ("FORBIDDEN", "Accès refusé"),
    404: ("NOT_FOUND", "Ressource introuvable"),
    405: ("VALIDATION_ERROR", "Méthode non autorisée sur cette ressource"),
}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def on_api_error(_: Request, exc: ApiError) -> JSONResponse:
        return error_response(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(DomainError)
    async def on_domain_error(_: Request, exc: DomainError) -> JSONResponse:
        return error_response(Conflict.status_code, Conflict.code, str(exc))

    @app.exception_handler(RequestValidationError)
    async def on_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = validation_details(list(exc.errors()))
        return error_response(400, ValidationFailed.code, ValidationFailed.default_message, details)

    @app.exception_handler(HTTPException)
    async def on_http_error(_: Request, exc: HTTPException) -> JSONResponse:
        if exc.status_code in _FRAMEWORK_ERRORS:
            code, message = _FRAMEWORK_ERRORS[exc.status_code]
        elif exc.status_code < 500:
            code, message = "VALIDATION_ERROR", str(exc.detail)
        else:
            code, message = "INTERNAL_ERROR", "Erreur interne"
        return error_response(exc.status_code, code, message)

    @app.exception_handler(Exception)
    async def on_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        # Starlette relance ensuite l'exception : le serveur journalise la trace complète.
        return error_response(500, "INTERNAL_ERROR", "Erreur interne, veuillez réessayer")
