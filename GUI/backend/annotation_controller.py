"""
Annotation controller -- HTTP client wrapper for the Flask annotation
server embedded in the remote Nerfstudio Viewer process.

All annotation commands go through HTTP POST requests to the Viewer's
daemon thread, forwarded locally via SSH port forwarding.
"""
from __future__ import annotations

import json
import urllib.request
import urllib.error
from typing import Callable

from shared.constants import NERFSTUDIO_ANNOTATION_TIMEOUT_S


class AnnotationController:
    """Sends HTTP requests to the remote Viewer's annotation HTTP server."""

    def __init__(self, local_port: int, log_callback: Callable[[str], None]):
        self._port = local_port
        self._log = log_callback
        self._base_url = f"http://localhost:{local_port}"

    # ------------------------------------------------------------------
    # Generic request helper
    # ------------------------------------------------------------------

    def _post(self, endpoint: str, data: dict | None = None) -> bool:
        """POST JSON to an annotation endpoint. Returns True on success."""
        url = f"{self._base_url}/annotation/{endpoint}"
        body = json.dumps(data or {}).encode("utf-8")
        req = urllib.request.Request(
            url, data=body, method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(
                req, timeout=NERFSTUDIO_ANNOTATION_TIMEOUT_S
            ) as resp:
                result = json.loads(resp.read().decode())
                if result.get("status") != "ok":
                    self._log(f"Annotation error ({endpoint}): {result}")
                    return False
                return True
        except urllib.error.URLError as exc:
            self._log(f"Annotation request failed ({endpoint}): {exc.reason}")
            return False
        except Exception as exc:
            self._log(f"Annotation request failed ({endpoint}): {exc}")
            return False

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def health_check(self) -> bool:
        """Check if the annotation server is responding."""
        url = f"{self._base_url}/health"
        try:
            with urllib.request.urlopen(
                url, timeout=NERFSTUDIO_ANNOTATION_TIMEOUT_S
            ) as resp:
                result = json.loads(resp.read().decode())
                return result.get("status") == "ok"
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Annotation commands
    # ------------------------------------------------------------------

    def set_scribble_enabled(self, enabled: bool) -> bool:
        return self._post("enable", {"enabled": enabled})

    def set_scribble_mode(self, mode: str) -> bool:
        return self._post("set_mode", {"mode": mode})

    def set_scribble_depth(self, depth: float) -> bool:
        return self._post("set_depth", {"depth": depth})

    def finish_stroke(self) -> bool:
        return self._post("finish")

    def clear_last_stroke(self) -> bool:
        return self._post("clear_last")

    def clear_all_strokes(self) -> bool:
        return self._post("clear_all")
