from __future__ import annotations

from app.core.settings import Settings
from app.schemas.contracts import EnsureContainerRequest


def _env_map(container) -> dict[str, str]:
    result: dict[str, str] = {}
    env_list = container.attrs.get("Config", {}).get("Env", []) or []
    for item in env_list:
        if "=" in item:
            k, v = item.split("=", 1)
            result[k] = v
    return result


def _network_aliases(container, network_name: str) -> list[str]:
    networks = container.attrs.get("NetworkSettings", {}).get("Networks", {})
    network = networks.get(network_name, {})
    return network.get("Aliases", []) or []


def detect_drift(container, req: EnsureContainerRequest, settings: Settings) -> list[str]:
    drifts: list[str] = []
    attrs = container.attrs
    image = attrs.get("Config", {}).get("Image")
    if image != settings.runtime_openclaw_image_ref:
        drifts.append("imageRef")

    cmd = attrs.get("Config", {}).get("Cmd", []) or []
    expected_cmd = settings.runtime_openclaw_command.split(" ")
    if cmd != expected_cmd:
        drifts.append("command")

    mounts = attrs.get("Mounts", []) or []
    mount_pairs = {(m.get("Source"), m.get("Destination")) for m in mounts}
    expected_pairs = {
        (req.compat.openclawConfigDir, "/home/node/.openclaw"),
        (req.compat.openclawWorkspaceDir, "/home/node/.openclaw/workspace"),
    }
    if not expected_pairs.issubset(mount_pairs):
        drifts.append("mounts")

    aliases = _network_aliases(container, settings.runtime_openclaw_network)
    expected_alias = f"rt-{req.runtimeId}"
    if expected_alias not in aliases:
        drifts.append("networkAlias")

    networks = attrs.get("NetworkSettings", {}).get("Networks", {})
    if settings.runtime_openclaw_network not in networks:
        drifts.append("network")

    labels = attrs.get("Config", {}).get("Labels", {}) or {}
    if labels.get("clawloops.configVersion") != req.renderedConfig.configVersion:
        drifts.append("configVersion")

    env = _env_map(container)
    expected_env = {
        "HOME": "/home/node",
        "TERM": "xterm-256color",
        "TZ": "UTC",
        "OPENAI_BASE_URL": "http://litellm:4000",
    }
    for key, value in expected_env.items():
        if env.get(key) != value:
            drifts.append(f"env:{key}")
            break
    return drifts
