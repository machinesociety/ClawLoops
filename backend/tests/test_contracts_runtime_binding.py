import json
from pathlib import Path

import pytest

from app.schemas.runtime import RuntimeBindingSnapshot, RuntimeStatusResponse
from app.schemas.workspace import WorkspaceEntryResponse


@pytest.mark.parametrize("baseline_version", ["baseline-v0.3", "baseline-v0.8"])
def test_user_runtime_binding_fields_match_contract(baseline_version: str):
    contracts_path = (
        Path(__file__).resolve().parents[2]
        / "contracts"
        / baseline_version
        / "user_runtime_binding.schema.json"
    )
    schema = json.loads(contracts_path.read_text(encoding="utf-8"))

    contract_fields = set(schema["properties"].keys())
    model_fields = set(RuntimeBindingSnapshot.model_fields.keys())

    assert model_fields == contract_fields


@pytest.mark.parametrize("baseline_version", ["baseline-v0.3", "baseline-v0.8"])
def test_runtime_status_projection_fields_match_api_boundary(baseline_version: str):
    contracts_path = (
        Path(__file__).resolve().parents[2]
        / "contracts"
        / baseline_version
        / "api-boundary.json"
    )
    boundary = json.loads(contracts_path.read_text(encoding="utf-8"))
    status_rule = next(rule for rule in boundary["rules"] if rule["id"] == "user_runtime_vs_status_boundary")

    assert set(RuntimeStatusResponse.model_fields.keys()) == set(status_rule["allowFields"])


def test_workspace_entry_does_not_expose_internal_endpoint():
    assert "internalEndpoint" not in WorkspaceEntryResponse.model_fields

