"""
Centralized constants and configuration for the LeEndoscope application.
"""
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent.parent  # LeEndoscope/
GUI_DIR = PROJECT_ROOT / "GUI"
DATA_DIR = PROJECT_ROOT / "Data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Default database paths
USER_DB_PATH = GUI_DIR / "db.db"
PATIENT_DB_PATH = GUI_DIR / "patients.db"
PATIENTS_JSON_PATH = GUI_DIR / "patients_data.json"
FRAME_SELECTION_PATH = PROJECT_ROOT / "frame_selection.json"

# Arduino sketch location
ARDUINO_CODE_DIR = PROJECT_ROOT / "ArduinoCode" / "sensorOutput"

# ---------------------------------------------------------------------------
# Recording / Camera
# ---------------------------------------------------------------------------
DEFAULT_RECORDING_FPS = 30
CAMERA_PROBE_MAX = 6
RECORD_TICK_MS = 10          # ms between recording-loop ticks
LIVE_PREVIEW_MS = 30         # ms between live-preview refreshes
CSV_FLUSH_INTERVAL_MS = 1000 # flush CSV buffers once per second

# ---------------------------------------------------------------------------
# Serial / IMU
# ---------------------------------------------------------------------------
SERIAL_BAUD_RATE = 115200
SERIAL_TIMEOUT = 0.5
IMU_SYNC_TIMEOUT_S = 0.6
IMU_SYNC_POLL_MS = 50
BNO_RESET_CHECK_MS = 100
BNO_RESET_TIMEOUT_S = 8.0
IMU_SAMPLES_PER_FRAME = 10  # number of nearest IMU samples to average

# ---------------------------------------------------------------------------
# Frame Quality Thresholds
# ---------------------------------------------------------------------------
SNR_THRESHOLD = 25
SHARPNESS_THRESHOLD = 100
BRIGHTNESS_THRESHOLD = 220
SATURATION_THRESHOLD = 40
SPECULAR_THRESHOLD = 0.05

# ---------------------------------------------------------------------------
# UI Geometry
# ---------------------------------------------------------------------------
GEOMETRY_DEBOUNCE_MS = 300
DEFAULT_WINDOW_WIDTH = 1000
DEFAULT_WINDOW_HEIGHT = 700

# ---------------------------------------------------------------------------
# Admin (can be overridden by LEENDOSCOPE_ADMIN_PASS env var)
# ---------------------------------------------------------------------------
import os
ADMIN_PASSWORD = os.environ.get("LEENDOSCOPE_ADMIN_PASS", "admin")

# ---------------------------------------------------------------------------
# Remote Server / Nerfstudio
# ---------------------------------------------------------------------------
NERFSTUDIO_SSH_HOST = os.environ.get("LEENDOSCOPE_SSH_HOST", "adax.cas.mcmaster.ca")
NERFSTUDIO_SSH_USER = os.environ.get("LEENDOSCOPE_SSH_USER", "divitob")
NERFSTUDIO_SSH_PORT = 22
NERFSTUDIO_WORKING_DIR = "/nfs/u50/capstone/mt4tb6g23/divitob"
NERFSTUDIO_CONDA_ENV = "nerfstudio"
NERFSTUDIO_DEFAULT_CONFIG_PATH = ""            # User fills in per-session
NERFSTUDIO_VIEWER_PORT = 7007                  # Default ns-viewer port on remote
NERFSTUDIO_LOCAL_PORT = 7010                   # Local port for SSH tunnel
NERFSTUDIO_VIEWER_STARTUP_TIMEOUT_S = 120      # Max wait for viewer to start
NERFSTUDIO_HEALTH_CHECK_INTERVAL_S = 15        # Seconds between health pings
