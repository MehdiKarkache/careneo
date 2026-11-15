"""L'API implémente exactement le contrat docs/openapi.yaml : mêmes routes, mêmes operationId,
mêmes gardes de rôle (x-roles) et mêmes routes publiques."""

from pathlib import Path
from typing import Any

import pytest
import yaml

from app.main import app

CONTRACT_PATH = Path(__file__).resolve().parents[2] / "docs" / "openapi.yaml"
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def operations(spec: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (method.upper(), path): operation
        for path, item in spec["paths"].items()
        for method, operation in item.items()
        if method in HTTP_METHODS
    }


CONTRACT = operations(yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8")))
IMPLEMENTATION = operations(app.openapi())


def test_the_api_exposes_exactly_the_contract_operations() -> None:
    assert set(IMPLEMENTATION) == set(CONTRACT)


@pytest.mark.parametrize("key", sorted(CONTRACT), ids=lambda key: f"{key[0]} {key[1]}")
def test_each_operation_matches_the_contract(key: tuple[str, str]) -> None:
    expected, actual = CONTRACT[key], IMPLEMENTATION[key]
    assert actual["operationId"] == expected["operationId"]
    assert set(actual.get("x-roles", [])) == set(expected.get("x-roles", []))
    is_public = expected.get("security") == []
    assert ("security" not in actual) == is_public
    success = {code for code in expected["responses"] if code.startswith("2")}
    assert success <= set(actual["responses"])
