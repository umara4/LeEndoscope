"""
Nerfstudio Reconstruction Viewer page (QWidget for embedding in AppShell).

Replaces the former PyVista point-cloud viewer. Connects to a remote server
via SSH, launches the Nerfstudio viewer (ns-viewer), tunnels the websocket
port locally, and displays the web-based viewer inside a QWebEngineView.
"""
from __future__ import annotations

from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QLineEdit, QTextEdit,
    QMessageBox, QInputDialog,
)
from PyQt6.QtCore import Qt, QUrl

from shared.theme import (
    SIDE_PANEL_STYLE, STYLE_VIEWER_CONTAINER, TERMINAL_DISPLAY_STYLE,
    STYLE_BOLD_LABEL, ACCENT_BUTTON_STYLE,
    STYLE_STATUS_CONNECTED, STYLE_STATUS_DISCONNECTED,
    STYLE_STATUS_ERROR, STYLE_STATUS_LOADING,
    BG_BASE, TEXT_SECONDARY,
)
from shared.constants import (
    NERFSTUDIO_SSH_HOST, NERFSTUDIO_SSH_USER, NERFSTUDIO_SSH_PORT,
    NERFSTUDIO_DEFAULT_CONFIG_PATH, NERFSTUDIO_VIEWER_PORT,
    NERFSTUDIO_LOCAL_PORT, NERFSTUDIO_HEALTH_CHECK_INTERVAL_S,
)

# QWebEngineView is optional -- gracefully degrade if not installed.
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    WEBENGINE_AVAILABLE = True
except ImportError:
    QWebEngineView = None
    WEBENGINE_AVAILABLE = False

# paramiko availability is checked at connection time via the worker.
try:
    from backend.ssh_service import (
        SSHConnectionWorker,
        NerfstudioViewerWorker,
        ViewerHealthChecker,
        PARAMIKO_AVAILABLE,
    )
except ImportError:
    PARAMIKO_AVAILABLE = False


class ReconstructionPage(QWidget):
    """Nerfstudio viewer page for 3D reconstruction visualization.

    Connects to the remote server via SSH, launches ns-viewer, and
    embeds the web viewer in a QWebEngineView.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # --- State ---
        self._ssh_client = None
        self._ssh_password: str | None = None
        self._viewer_worker: NerfstudioViewerWorker | None = None
        self._health_checker: ViewerHealthChecker | None = None
        self._connection_worker: SSHConnectionWorker | None = None
        self._viewer_url: str | None = None
        self._is_connected = False
        self._is_viewer_running = False

        self._build_ui()

    # ==================================================================
    # UI Construction
    # ==================================================================

    def _build_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(8)

        # ---------- Side panel (stretch=1) ----------
        side_panel = QFrame(self)
        side_panel.setStyleSheet(SIDE_PANEL_STYLE)
        side_layout = QVBoxLayout(side_panel)
        side_layout.setContentsMargins(10, 10, 10, 10)
        side_layout.setSpacing(6)

        # -- SSH connection section --
        ssh_header = QLabel("Remote Server")
        ssh_header.setStyleSheet(STYLE_BOLD_LABEL)
        side_layout.addWidget(ssh_header)

        self._host_label = QLabel(f"Host: {NERFSTUDIO_SSH_HOST}")
        self._host_label.setWordWrap(True)
        side_layout.addWidget(self._host_label)

        self._connect_btn = QPushButton("Connect to Server")
        self._connect_btn.setStyleSheet(ACCENT_BUTTON_STYLE)
        self._connect_btn.setFixedHeight(34)
        self._connect_btn.clicked.connect(self._on_connect_clicked)
        side_layout.addWidget(self._connect_btn)

        self._connection_status = QLabel("Disconnected")
        self._connection_status.setStyleSheet(STYLE_STATUS_DISCONNECTED)
        self._connection_status.setWordWrap(True)
        side_layout.addWidget(self._connection_status)

        # Subtle divider
        divider1 = QFrame()
        divider1.setFrameShape(QFrame.Shape.HLine)
        divider1.setFixedHeight(1)
        side_layout.addWidget(divider1)

        # -- Nerfstudio viewer section --
        viewer_header = QLabel("Nerfstudio Viewer")
        viewer_header.setStyleSheet(STYLE_BOLD_LABEL)
        side_layout.addWidget(viewer_header)

        config_label = QLabel("Config path (remote):")
        side_layout.addWidget(config_label)

        self._config_input = QLineEdit()
        self._config_input.setText(NERFSTUDIO_DEFAULT_CONFIG_PATH)
        self._config_input.setPlaceholderText("/path/to/outputs/.../config.yml")
        side_layout.addWidget(self._config_input)

        # Button row: Launch | Stop
        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)

        self._launch_btn = QPushButton("Launch Viewer")
        self._launch_btn.setFixedHeight(34)
        self._launch_btn.setEnabled(False)
        self._launch_btn.clicked.connect(self._on_launch_clicked)
        btn_row.addWidget(self._launch_btn)

        self._stop_btn = QPushButton("Stop Viewer")
        self._stop_btn.setFixedHeight(34)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._on_stop_clicked)
        btn_row.addWidget(self._stop_btn)

        side_layout.addLayout(btn_row)

        self._reload_btn = QPushButton("Reload Page")
        self._reload_btn.setFixedHeight(34)
        self._reload_btn.setEnabled(False)
        self._reload_btn.clicked.connect(self._on_reload_clicked)
        side_layout.addWidget(self._reload_btn)

        self._viewer_status = QLabel("Viewer: Not running")
        self._viewer_status.setStyleSheet(STYLE_STATUS_DISCONNECTED)
        self._viewer_status.setWordWrap(True)
        side_layout.addWidget(self._viewer_status)

        # Subtle divider
        divider2 = QFrame()
        divider2.setFrameShape(QFrame.Shape.HLine)
        divider2.setFixedHeight(1)
        side_layout.addWidget(divider2)

        # -- Log panel --
        log_label = QLabel("Log")
        log_label.setStyleSheet(STYLE_BOLD_LABEL)
        side_layout.addWidget(log_label)

        self._log_display = QTextEdit()
        self._log_display.setReadOnly(True)
        self._log_display.setStyleSheet(TERMINAL_DISPLAY_STYLE)
        side_layout.addWidget(self._log_display, stretch=1)

        # ---------- Viewer container (stretch=4) ----------
        viewer_container = QWidget(self)
        viewer_container.setStyleSheet(STYLE_VIEWER_CONTAINER)
        viewer_layout = QVBoxLayout(viewer_container)
        viewer_layout.setContentsMargins(0, 0, 0, 0)

        self._placeholder = QLabel(
            "Connect to server and launch the Nerfstudio viewer\n"
            "to see your 3D reconstruction here."
        )
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet(
            f"background-color: {BG_BASE}; color: {TEXT_SECONDARY}; "
            f"border: none; font-size: 14px;"
        )

        self._web_view = None
        if WEBENGINE_AVAILABLE:
            self._web_view = QWebEngineView(viewer_container)
            self._web_view.setVisible(False)
            viewer_layout.addWidget(self._web_view, stretch=1)
        viewer_layout.addWidget(self._placeholder, stretch=1)

        main_layout.addWidget(side_panel, stretch=1)
        main_layout.addWidget(viewer_container, stretch=4)

        # -- Availability checks --
        if not WEBENGINE_AVAILABLE:
            self._log("PyQt6-WebEngine is not installed.")
            self._connect_btn.setEnabled(False)
            QMessageBox.information(
                self, "Missing Dependency",
                "PyQt6-WebEngine is required for the Nerfstudio viewer.\n"
                "Install with: pip install PyQt6-WebEngine",
            )
        if not PARAMIKO_AVAILABLE:
            self._log("paramiko is not installed.")
            self._connect_btn.setEnabled(False)

    # ==================================================================
    # Logging helper
    # ==================================================================

    def _log(self, message: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self._log_display.append(f"[{ts}] {message}")
        # Auto-scroll to bottom
        sb = self._log_display.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())

    # ==================================================================
    # SSH Connection
    # ==================================================================

    def _on_connect_clicked(self):
        if self._is_connected:
            self._disconnect_ssh()
            return

        # Prompt for password (reuse cached if available)
        if not self._ssh_password:
            password, ok = QInputDialog.getText(
                self, "SSH Password",
                f"Password for {NERFSTUDIO_SSH_USER}@{NERFSTUDIO_SSH_HOST}:",
                QLineEdit.EchoMode.Password,
            )
            if not ok or not password:
                self._log("Connection cancelled.")
                return
            self._ssh_password = password

        self._connect_btn.setEnabled(False)
        self._connection_status.setText("Connecting...")
        self._connection_status.setStyleSheet(STYLE_STATUS_LOADING)
        self._log(f"Connecting to {NERFSTUDIO_SSH_HOST}...")

        self._connection_worker = SSHConnectionWorker(
            NERFSTUDIO_SSH_HOST, NERFSTUDIO_SSH_USER,
            self._ssh_password, NERFSTUDIO_SSH_PORT,
        )
        self._connection_worker.connected.connect(self._on_ssh_connected)
        self._connection_worker.connection_failed.connect(self._on_ssh_failed)
        self._connection_worker.start()

    def _on_ssh_connected(self, client):
        self._ssh_client = client
        self._is_connected = True
        self._connect_btn.setEnabled(True)
        self._connect_btn.setText("Disconnect")
        self._launch_btn.setEnabled(True)
        self._connection_status.setText(f"Connected to {NERFSTUDIO_SSH_HOST}")
        self._connection_status.setStyleSheet(STYLE_STATUS_CONNECTED)
        self._log("SSH connection established.")

    def _on_ssh_failed(self, error_msg: str):
        self._ssh_password = None  # clear bad password
        self._connect_btn.setEnabled(True)
        self._connection_status.setText(f"Failed: {error_msg}")
        self._connection_status.setStyleSheet(STYLE_STATUS_ERROR)
        self._log(f"Connection failed: {error_msg}")
        QMessageBox.warning(self, "SSH Connection Failed", error_msg)

    def _disconnect_ssh(self):
        self._stop_viewer()
        if self._ssh_client:
            try:
                self._ssh_client.close()
            except Exception:
                pass
            self._ssh_client = None
        self._is_connected = False
        self._connect_btn.setText("Connect to Server")
        self._launch_btn.setEnabled(False)
        self._connection_status.setText("Disconnected")
        self._connection_status.setStyleSheet(STYLE_STATUS_DISCONNECTED)
        self._log("Disconnected from server.")

    # ==================================================================
    # Viewer Launch / Stop
    # ==================================================================

    def _on_launch_clicked(self):
        config_path = self._config_input.text().strip()
        if not config_path:
            QMessageBox.warning(
                self, "Missing Config",
                "Enter the remote path to a Nerfstudio config file.",
            )
            return

        if not self._ssh_client:
            QMessageBox.warning(self, "Not Connected", "Connect to the server first.")
            return

        self._launch_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._viewer_status.setText("Starting viewer...")
        self._viewer_status.setStyleSheet(STYLE_STATUS_LOADING)
        self._log(f"Launching ns-viewer with config: {config_path}")

        self._viewer_worker = NerfstudioViewerWorker(
            ssh_client=self._ssh_client,
            config_path=config_path,
            remote_host=NERFSTUDIO_SSH_HOST,
            local_port=NERFSTUDIO_LOCAL_PORT,
            viewer_port=NERFSTUDIO_VIEWER_PORT,
        )
        self._viewer_worker.output_line.connect(self._on_viewer_output)
        self._viewer_worker.viewer_ready.connect(self._on_viewer_ready)
        self._viewer_worker.viewer_failed.connect(self._on_viewer_failed)
        self._viewer_worker.viewer_stopped.connect(self._on_viewer_stopped)
        self._viewer_worker.start()

    def _on_viewer_output(self, line: str):
        self._log(line)

    def _on_viewer_ready(self, url: str):
        self._viewer_url = url
        self._is_viewer_running = True
        self._reload_btn.setEnabled(True)
        self._viewer_status.setText(f"Running at {url}")
        self._viewer_status.setStyleSheet(STYLE_STATUS_CONNECTED)
        self._log(f"Viewer ready at {url}")

        # Load the viewer URL in QWebEngineView
        if self._web_view:
            self._web_view.setUrl(QUrl(url))
            self._web_view.setVisible(True)
            self._placeholder.setVisible(False)

        # Start health monitoring
        self._health_checker = ViewerHealthChecker(
            url, interval_s=NERFSTUDIO_HEALTH_CHECK_INTERVAL_S,
        )
        self._health_checker.health_check_failed.connect(self._on_health_failed)
        self._health_checker.start()

    def _on_viewer_failed(self, error: str):
        self._is_viewer_running = False
        self._launch_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._reload_btn.setEnabled(False)
        self._viewer_status.setText(f"Failed: {error}")
        self._viewer_status.setStyleSheet(STYLE_STATUS_ERROR)
        self._log(f"Viewer failed: {error}")
        self._show_placeholder()
        QMessageBox.warning(self, "Viewer Error", error)

    def _on_viewer_stopped(self):
        self._is_viewer_running = False
        self._launch_btn.setEnabled(self._is_connected)
        self._stop_btn.setEnabled(False)
        self._reload_btn.setEnabled(False)
        self._viewer_status.setText("Viewer stopped")
        self._viewer_status.setStyleSheet(STYLE_STATUS_DISCONNECTED)
        self._log("Viewer stopped.")
        self._show_placeholder()

    def _on_stop_clicked(self):
        self._log("Stopping viewer...")
        self._stop_viewer()

    def _stop_viewer(self):
        # Stop health checker
        if self._health_checker and self._health_checker.isRunning():
            self._health_checker.request_stop()
            self._health_checker.wait(2000)
        self._health_checker = None

        # Stop viewer worker
        if self._viewer_worker and self._viewer_worker.isRunning():
            self._viewer_worker.request_stop()
            self._viewer_worker.wait(5000)
        self._viewer_worker = None

        self._is_viewer_running = False
        self._viewer_url = None
        self._launch_btn.setEnabled(self._is_connected)
        self._stop_btn.setEnabled(False)
        self._reload_btn.setEnabled(False)
        self._viewer_status.setText("Viewer: Not running")
        self._viewer_status.setStyleSheet(STYLE_STATUS_DISCONNECTED)
        self._show_placeholder()

    def _show_placeholder(self):
        if self._web_view:
            self._web_view.setVisible(False)
        self._placeholder.setVisible(True)

    # ==================================================================
    # Reload / Health
    # ==================================================================

    def _on_reload_clicked(self):
        if self._web_view and self._viewer_url:
            self._log("Reloading viewer page.")
            self._web_view.reload()

    def _on_health_failed(self, reason: str):
        self._viewer_status.setText(f"Warning: {reason}")
        self._viewer_status.setStyleSheet(STYLE_STATUS_ERROR)
        self._log(f"Health check: {reason}")

    # ==================================================================
    # Cleanup (called by AppShell on logout / window close)
    # ==================================================================

    def cleanup(self):
        self._stop_viewer()
        if self._ssh_client:
            try:
                self._ssh_client.close()
            except Exception:
                pass
            self._ssh_client = None
        self._is_connected = False
