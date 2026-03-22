"""
Persistent server configuration storage.

Saves and loads remote server settings (hostname, username, etc.) to a JSON
file alongside the GUI directory, following the geometry_store.py pattern.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

_CONFIG_FILE = Path(__file__).parent.parent / "server_config.json"

_DEFAULTS = {
    "hostname": "",
    "port": 22,
    "username": "",
    "remote_workdir": "",
    "viewer_port": 7007,
    "conda_env": "nerfstudio",
}


def save_server_config(config: dict) -> None:
    """Persist server configuration to disk."""
    _CONFIG_FILE.write_text(json.dumps(config, indent=2), encoding="utf-8")


def load_server_config() -> dict:
    """Load saved server configuration, falling back to defaults."""
    if not _CONFIG_FILE.exists():
        return dict(_DEFAULTS)
    try:
        data = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
        merged = dict(_DEFAULTS)
        merged.update(data)
        return merged
    except Exception:
        return dict(_DEFAULTS)
