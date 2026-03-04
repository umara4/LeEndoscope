"""
Persistent window geometry storage with debounced saves.

All windows use this module to save/restore their position and size.
Saves are debounced so that during drag/resize (dozens of events per second),
only the final position is written to disk.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Optional, Tuple

_STORE_FILE = Path(__file__).parent.parent / "geometry_store.geometry.json"


def save_geometry(geom: Tuple[int, int, int, int]) -> None:
    """Save window geometry (x, y, w, h) to the JSON store."""
    data = _read_store()
    data["geometry"] = {"x": geom[0], "y": geom[1], "w": geom[2], "h": geom[3]}
    _write_store(data)


def load_geometry() -> Optional[Tuple[int, int, int, int]]:
    """Load saved window geometry or None if not available."""
    data = _read_store()
    g = data.get("geometry")
    if not g:
        return None
    return (g["x"], g["y"], g["w"], g["h"])


def save_start_size(w: int, h: int) -> None:
    """Save the default start size for new sessions."""
    data = _read_store()
    data["start_size"] = {"w": w, "h": h}
    _write_store(data)


def get_start_size() -> Optional[Tuple[int, int]]:
    """Get the saved default start size or None."""
    data = _read_store()
    s = data.get("start_size")
    if not s:
        return None
    return (s["w"], s["h"])


def _read_store() -> dict:
    if not _STORE_FILE.exists():
        return {}
    try:
        return json.loads(_STORE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_store(data: dict) -> None:
    _STORE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
