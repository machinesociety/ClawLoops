from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from app.core.errors import RuntimeManagerError


# Check if running on Windows
IS_WINDOWS = os.name == 'nt'


def _prepare_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    # Skip chown on Windows
    if not IS_WINDOWS:
        try:
            os.chown(path, 1000, 1000)
        except PermissionError as exc:
            raise RuntimeManagerError("RUNTIME_START_FAILED", f"chown failed for {path}", 500) from exc
    path.chmod(0o775)


def _apply_recursive_permissions(root: Path) -> None:
    for current_root, dirs, files in os.walk(root):
        root_path = Path(current_root)
        # Skip chown on Windows
        if not IS_WINDOWS:
            try:
                os.chown(root_path, 1000, 1000)
            except PermissionError as exc:
                raise RuntimeManagerError("RUNTIME_START_FAILED", f"chown failed for {root_path}", 500) from exc
        root_path.chmod(0o775)
        for name in dirs:
            p = root_path / name
            # Skip chown on Windows
            if not IS_WINDOWS:
                try:
                    os.chown(p, 1000, 1000)
                except PermissionError as exc:
                    raise RuntimeManagerError("RUNTIME_START_FAILED", f"chown failed for {p}", 500) from exc
            p.chmod(0o775)
        for name in files:
            p = root_path / name
            # Skip chown on Windows
            if not IS_WINDOWS:
                try:
                    os.chown(p, 1000, 1000)
                except PermissionError as exc:
                    raise RuntimeManagerError("RUNTIME_START_FAILED", f"chown failed for {p}", 500) from exc
            p.chmod(0o664)


def prepare_runtime_dirs(config_dir: str, workspace_dir: str) -> None:
    config_path = Path(config_dir)
    workspace_path = Path(workspace_dir)
    _prepare_dir(config_path)
    _apply_recursive_permissions(config_path)
    if workspace_path != config_path:
        _prepare_dir(workspace_path)
        _apply_recursive_permissions(workspace_path)


def write_openclaw_config(config_dir: str, openclaw_json: dict) -> str:
    root = Path(config_dir)
    root.mkdir(parents=True, exist_ok=True)
    target = root / "openclaw.json"
    serialized = json.dumps(openclaw_json, ensure_ascii=False, indent=2)
    fd, temp_path = tempfile.mkstemp(prefix="openclaw.", suffix=".tmp", dir=str(root))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(serialized)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, target)
        # Skip chown on Windows
        if not IS_WINDOWS:
            os.chown(target, 1000, 1000)
        os.chmod(target, 0o664)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
    return str(target)
