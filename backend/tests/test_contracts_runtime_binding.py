import json
from pathlib import Path

from app.schemas.runtime import UserRuntimeBinding


def test_user_runtime_binding_fields_match_contract():
    contracts_path = (
        Path(__file__).resolve().parents[2]
        / "contracts"
        / "baseline-v0.2"
        / "user_runtime_binding.schema.json"
    )
    schema = json.loads(contracts_path.read_text(encoding="utf-8"))

    contract_fields = set(schema["properties"].keys())
    model_fields = set(UserRuntimeBinding.model_fields.keys())

    assert model_fields == contract_fields

