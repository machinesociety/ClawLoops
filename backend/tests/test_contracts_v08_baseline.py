import json
from pathlib import Path


def _read_contract_file(filename: str) -> dict:
    path = Path(__file__).resolve().parents[2] / "contracts" / "baseline-v0.8" / filename
    return json.loads(path.read_text(encoding="utf-8"))


def test_v08_contract_files_exist_and_version_is_consistent():
    baseline = _read_contract_file("enums.json")
    errors = _read_contract_file("errors.json")
    boundary = _read_contract_file("api-boundary.json")
    schema = _read_contract_file("user_runtime_binding.schema.json")

    assert baseline["baselineVersion"] == "v0.8"
    assert errors["baselineVersion"] == "v0.8"
    assert boundary["baselineVersion"] == "v0.8"
    assert schema["$id"].endswith(":baseline-v0.8:UserRuntimeBinding")


def test_v08_invitation_status_enum_is_frozen():
    enums = _read_contract_file("enums.json")["enums"]
    assert enums["invitation.status"] == ["pending", "consumed", "revoked"]


def test_v08_error_registry_contains_required_new_codes():
    error_codes = {entry["code"] for entry in _read_contract_file("errors.json")["errors"]}
    required_codes = {
        "INVITATION_NOT_FOUND",
        "INVITATION_ALREADY_CONSUMED",
        "INVITATION_REVOKED",
        "INVITATION_EXPIRED",
        "INVITATION_EMAIL_MISMATCH",
        "INVITATION_WORKSPACE_INVALID",
        "RUNTIME_CONTRACT_DRIFT",
        "RUNTIME_START_FAILED",
        "RUNTIME_STOP_FAILED",
        "RUNTIME_DELETE_FAILED",
        "INVITATION_ERROR",
        "USER_SYNC_ERROR",
    }
    assert required_codes.issubset(error_codes)


def test_v08_boundary_contains_runtime_delete_and_auth_access_rules():
    rules = _read_contract_file("api-boundary.json")["rules"]
    rule_ids = {rule["id"] for rule in rules}
    assert "runtime_delete_post_only" in rule_ids
    assert "auth_access_always_200" in rule_ids

    delete_rule = next(rule for rule in rules if rule["id"] == "runtime_delete_post_only")
    assert "POST /api/v1/users/me/runtime/delete" in delete_rule["appliesTo"]
    assert "DELETE /api/v1/users/me/runtime" in delete_rule["forbidPaths"]


def test_v08_runtime_manager_rule_forbids_image_ref_and_requires_compat():
    rules = _read_contract_file("api-boundary.json")["rules"]
    rm_rule = next(
        rule for rule in rules if rule["id"] == "runtime_manager_ensure_running_forbid_image_ref"
    )

    assert "imageRef" in rm_rule["forbidRequestFields"]
    assert "compat.openclawConfigDir" in rm_rule["requireRequestFields"]
    assert "compat.openclawWorkspaceDir" in rm_rule["requireRequestFields"]
