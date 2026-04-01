"""
Nerfstudio Reconstruction page (QWidget for embedding in AppShell).

Connects to a remote server via SSH, starts NerfStudio training on
data already present on the server, and opens the Nerfstudio viewer
in the system browser for interactive 3D viewing.

Also supports manually launching ns-viewer for previously trained models.
"""
from __future__ import annotations

import socket
import threading
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QLineEdit, QTextEdit,
    QMessageBox,
)
from PyQt6.QtCore import Qt, QUrl, QSize, pyqtSignal
from PyQt6.QtGui import QPixmap, QPainter, QColor, QIcon

from shared.theme import (
    SIDE_PANEL_STYLE, STYLE_VIEWER_CONTAINER, TERMINAL_DISPLAY_STYLE,
    STYLE_BOLD_LABEL, ACCENT_BUTTON_STYLE,
    STYLE_STATUS_CONNECTED, STYLE_STATUS_DISCONNECTED,
    STYLE_STATUS_ERROR, STYLE_STATUS_LOADING,
    BG_BASE, TEXT_SECONDARY, VIEWER_BG, BORDER_PANEL,
)
from shared.form_helpers import set_button_enabled_style
from shared.constants import (
    NERFSTUDIO_SSH_HOST, NERFSTUDIO_SSH_USER, NERFSTUDIO_SSH_PORT,
    NERFSTUDIO_VIEWER_PORT,
    NERFSTUDIO_LOCAL_PORT, NERFSTUDIO_HEALTH_CHECK_INTERVAL_S,
    NERFSTUDIO_WORKING_DIR, NERFSTUDIO_CONDA_ENV,
    NERFSTUDIO_ANNOTATION_PORT, NERFSTUDIO_LOCAL_ANNOTATION_PORT,
)

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

# QWebEngineView is optional -- gracefully degrade if not installed.
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEngineSettings
    WEBENGINE_AVAILABLE = True
except ImportError:
    QWebEngineView = None
    QWebEngineSettings = None
    WEBENGINE_AVAILABLE = False

try:
    from backend.nerfstudio_service import NerfstudioTrainWorker
except ImportError:
    NerfstudioTrainWorker = None

from backend.annotation_controller import AnnotationController
from frontend.reconstruction.annotations_panel import AnnotationsPanel


class ReconstructionPage(QWidget):
    """Nerfstudio reconstruction page: connect, train, and view."""

    navigate_to_export = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # --- Patient context ---
        self._export_dir: Path | None = None

        # --- State ---
        self._ssh_client = None
        self._health_checker: ViewerHealthChecker | None = None
        self._connection_worker: SSHConnectionWorker | None = None
        self._train_worker: NerfstudioTrainWorker | None = None
        self._viewer_url: str | None = None
        self._is_connected = False
        self._is_viewer_running = False
        self._forward_server: socket.socket | None = None
        self._tunnel_stop: threading.Event | None = None

        # Collapsible section state
        self._conn_collapsed = True
        self._train_collapsed = True
        self._annotations_collapsed = True
        self._terminal_collapsed = False  # starts expanded

        # Training camera visibility
        self._train_cams_visible = True

        # Annotation state
        self._annotations_controller: AnnotationController | None = None
        self._annotation_tunnel_server: socket.socket | None = None
        self._annotation_tunnel_stop: threading.Event | None = None

        self._build_ui()

    # ==================================================================
    # Public: receive session info from ImagingPage
    # ==================================================================

    def set_session_info(self, info: dict):
        """Accept session info from imaging page."""
        terminal_log = info.get("terminal_log", "")
        if terminal_log:
            self._log_display.append(terminal_log)
            self._log_display.append("--- Imaging session log above ---\n")
            sb = self._log_display.verticalScrollBar()
            if sb:
                sb.setValue(sb.maximum())
        # Set export dir from session directory
        session_dir = info.get("session_dir")
        if session_dir:
            export_dir = Path(session_dir) / "Export"
            self.set_patient_export_dir(export_dir)

    def set_patient_export_dir(self, export_dir: Path):
        """Set the per-patient Export directory for screenshots."""
        self._export_dir = export_dir
        self._export_dir.mkdir(parents=True, exist_ok=True)

    # ==================================================================
    # UI Construction
    # ==================================================================

    def _build_ui(self):
        main_layout = QHBoxLayout(self)

        # ---------- Side panel (QFrame, fixed width, matches Imaging) ----------
        side_panel = QFrame(self)
        side_panel.setStyleSheet(SIDE_PANEL_STYLE)
        side_panel.setFixedWidth(240)
        side_layout = QVBoxLayout(side_panel)

        # -- Connection (collapsible) --
        self._conn_btn = QPushButton("Connection")
        self._conn_btn.setFixedHeight(40)
        self._conn_btn.setIcon(self._make_circle_icon("#6C6C80"))
        self._conn_btn.setIconSize(QSize(10, 10))
        self._conn_btn.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._conn_btn.clicked.connect(self._toggle_connection)
        side_layout.addWidget(self._conn_btn)

        self._conn_content = QWidget()
        conn_layout = QVBoxLayout(self._conn_content)
        conn_layout.setContentsMargins(5, 5, 5, 5)
        conn_layout.setSpacing(6)

        host_label = QLabel("Host:")
        host_label.setStyleSheet(STYLE_BOLD_LABEL)
        conn_layout.addWidget(host_label)
        self._host_input = QLineEdit()
        self._host_input.setText(NERFSTUDIO_SSH_HOST)
        self._host_input.setPlaceholderText("hostname")
        conn_layout.addWidget(self._host_input)

        user_label = QLabel("Username:")
        user_label.setStyleSheet(STYLE_BOLD_LABEL)
        conn_layout.addWidget(user_label)
        self._user_input = QLineEdit()
        self._user_input.setText(NERFSTUDIO_SSH_USER)
        self._user_input.setPlaceholderText("username")
        conn_layout.addWidget(self._user_input)

        pass_label = QLabel("Password:")
        pass_label.setStyleSheet(STYLE_BOLD_LABEL)
        conn_layout.addWidget(pass_label)
        self._pass_input = QLineEdit()
        self._pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._pass_input.setPlaceholderText("password")
        conn_layout.addWidget(self._pass_input)

        self._connect_btn = QPushButton("Connect")
        self._connect_btn.setStyleSheet(ACCENT_BUTTON_STYLE)
        self._connect_btn.clicked.connect(self._on_connect_clicked)
        conn_layout.addWidget(self._connect_btn)

        self._conn_content.setVisible(False)
        side_layout.addWidget(self._conn_content)

        # -- Train Model (collapsible) --
        self._train_toggle_btn = QPushButton("Train Model")
        self._train_toggle_btn.setFixedHeight(40)
        self._train_toggle_btn.clicked.connect(self._toggle_train)
        side_layout.addWidget(self._train_toggle_btn)

        self._train_content = QWidget()
        train_layout = QVBoxLayout(self._train_content)
        train_layout.setContentsMargins(5, 5, 5, 5)
        train_layout.setSpacing(6)

        train_folder_label = QLabel("Nerfstudio Data Folder:")
        train_folder_label.setStyleSheet(STYLE_BOLD_LABEL)
        train_layout.addWidget(train_folder_label)

        self._train_folder_input = QLineEdit()
        self._train_folder_input.setPlaceholderText("Cylinder")
        self._train_folder_input.setText("Cylinder")
        train_layout.addWidget(self._train_folder_input)

        train_row = QHBoxLayout()

        self._train_btn = QPushButton("Start Training")
        self._train_btn.setStyleSheet(ACCENT_BUTTON_STYLE)
        self._train_btn.setEnabled(False)
        set_button_enabled_style(self._train_btn, False)
        self._train_btn.clicked.connect(self._on_start_training)
        train_row.addWidget(self._train_btn)

        self._stop_train_btn = QPushButton("Stop")
        self._stop_train_btn.setEnabled(False)
        set_button_enabled_style(self._stop_train_btn, False)
        self._stop_train_btn.clicked.connect(self._on_stop_training)
        train_row.addWidget(self._stop_train_btn)

        train_layout.addLayout(train_row)

        self._train_stage = QLabel("")
        self._train_stage.setWordWrap(True)
        train_layout.addWidget(self._train_stage)

        self._train_content.setVisible(False)
        side_layout.addWidget(self._train_content)

        # -- Reload Viewer --
        self._reload_btn = QPushButton("Reload Viewer")
        self._reload_btn.setFixedHeight(40)
        self._reload_btn.setEnabled(False)
        set_button_enabled_style(self._reload_btn, False)
        self._reload_btn.clicked.connect(self._on_reload_clicked)
        side_layout.addWidget(self._reload_btn)

        # -- Toggle Training Images --
        self._toggle_cams_btn = QPushButton("Toggle Training Images")
        self._toggle_cams_btn.setFixedHeight(40)
        self._toggle_cams_btn.setEnabled(False)
        set_button_enabled_style(self._toggle_cams_btn, False)
        self._toggle_cams_btn.clicked.connect(self._on_toggle_training_cams)
        side_layout.addWidget(self._toggle_cams_btn)

        self._viewer_status = QLabel("Viewer: Not running")
        self._viewer_status.setStyleSheet(STYLE_STATUS_DISCONNECTED)
        self._viewer_status.setWordWrap(True)
        side_layout.addWidget(self._viewer_status)

        # -- Annotations (collapsible) --
        self._annotations_btn = QPushButton("Annotations")
        self._annotations_btn.setFixedHeight(40)
        self._annotations_btn.setIcon(self._make_circle_icon("#6C6C80"))
        self._annotations_btn.setIconSize(QSize(10, 10))
        self._annotations_btn.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._annotations_btn.clicked.connect(self._toggle_annotations)
        self._annotations_btn.setEnabled(False)
        side_layout.addWidget(self._annotations_btn)

        self._annotations_content = QWidget()
        annotations_layout = QVBoxLayout(self._annotations_content)
        annotations_layout.setContentsMargins(5, 5, 5, 5)
        annotations_layout.setSpacing(6)

        self._annotations_panel = AnnotationsPanel()
        self._annotations_panel.set_controller(None)
        self._annotations_panel.screenshot_requested.connect(self._on_screenshot)
        annotations_layout.addWidget(self._annotations_panel)

        self._annotations_content.setVisible(False)
        side_layout.addWidget(self._annotations_content)

        # -- Export button --
        self._export_btn = QPushButton("Export")
        self._export_btn.setFixedHeight(40)
        self._export_btn.clicked.connect(self.navigate_to_export.emit)
        side_layout.addWidget(self._export_btn)

        # -- Terminal (collapsible, starts expanded) --
        self._terminal_btn = QPushButton("Terminal \u25bc")
        self._terminal_btn.setFixedHeight(40)
        self._terminal_btn.clicked.connect(self._toggle_terminal)
        side_layout.addWidget(self._terminal_btn)

        self._log_display = QTextEdit()
        self._log_display.setReadOnly(True)
        self._log_display.setStyleSheet(TERMINAL_DISPLAY_STYLE)
        self._log_display.setVisible(True)
        side_layout.addWidget(self._log_display, 10)

        # Bottom stretch keeps buttons packed toward top when sections are closed
        side_layout.addStretch(1)

        # ---------- Viewer container (stretch=1, fills remaining space) ----------
        viewer_container = QWidget(self)
        viewer_container.setStyleSheet(STYLE_VIEWER_CONTAINER)
        viewer_layout = QVBoxLayout(viewer_container)
        viewer_layout.setContentsMargins(0, 0, 0, 0)

        self._placeholder = QLabel(
            "Connect to server and start training.\n"
            "The viewer will open automatically once training begins."
        )
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet(
            f"background-color: {VIEWER_BG}; color: {TEXT_SECONDARY}; "
            f"border: 1px solid {BORDER_PANEL}; font-size: 14px;"
        )

        self._web_view = None
        if WEBENGINE_AVAILABLE:
            self._web_view = QWebEngineView(viewer_container)
            # Enable WebGL, JS, and local->remote URL access for viser viewer
            settings = self._web_view.settings()
            settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
            self._web_view.setVisible(False)
            viewer_layout.addWidget(self._web_view, stretch=1)
        viewer_layout.addWidget(self._placeholder, stretch=1)

        main_layout.addWidget(side_panel, 0)
        main_layout.addWidget(viewer_container, 1)

        # -- Availability checks --
        if not WEBENGINE_AVAILABLE:
            self._log("PyQt6-WebEngine not available; embedded viewer disabled.")
        if not PARAMIKO_AVAILABLE:
            self._log("paramiko is not installed.")
            self._connect_btn.setEnabled(False)

    # ==================================================================
    # Collapsible section toggles
    # ==================================================================

    def _toggle_connection(self):
        self._conn_collapsed = not self._conn_collapsed
        self._conn_content.setVisible(not self._conn_collapsed)
        self._conn_btn.setText(
            "Connection \u25bc" if not self._conn_collapsed else "Connection"
        )

    def _toggle_train(self):
        self._train_collapsed = not self._train_collapsed
        self._train_content.setVisible(not self._train_collapsed)
        self._train_toggle_btn.setText(
            "Train Model \u25bc" if not self._train_collapsed else "Train Model"
        )

    def _toggle_annotations(self):
        self._annotations_collapsed = not self._annotations_collapsed
        self._annotations_content.setVisible(not self._annotations_collapsed)
        self._annotations_btn.setText(
            "Annotations \u25bc" if not self._annotations_collapsed else "Annotations"
        )

    def _toggle_terminal(self):
        self._terminal_collapsed = not self._terminal_collapsed
        self._log_display.setVisible(not self._terminal_collapsed)
        self._terminal_btn.setText(
            "Terminal \u25bc" if not self._terminal_collapsed else "Terminal"
        )

    # ==================================================================
    # Logging helper
    # ==================================================================

    def _log(self, message: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self._log_display.append(f"[{ts}] {message}")
        sb = self._log_display.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())

    # ==================================================================
    # Connection status helpers
    # ==================================================================

    def _set_status(self, text: str, style: str, color: str):
        self._conn_btn.setIcon(self._make_circle_icon(color))

    @staticmethod
    def _make_circle_icon(color: str) -> QIcon:
        """Return a QIcon containing a small filled circle of the given color."""
        size = 10
        pixmap = QPixmap(size, size)
        pixmap.fill(QColor("transparent"))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(color))
        painter.setPen(QColor(color))
        painter.drawEllipse(0, 0, size, size)
        painter.end()
        return QIcon(pixmap)

    def _update_train_enabled(self):
        set_button_enabled_style(self._train_btn, self._is_connected)

    # ==================================================================
    # SSH Connection
    # ==================================================================

    def _on_connect_clicked(self):
        if self._is_connected:
            self._disconnect_ssh()
            return

        host = self._host_input.text().strip()
        username = self._user_input.text().strip()
        password = self._pass_input.text()

        if not host or not username:
            QMessageBox.warning(self, "Missing Fields", "Enter host and username.")
            return
        if not password:
            QMessageBox.warning(self, "Missing Password", "Enter the SSH password.")
            return

        self._connect_btn.setEnabled(False)
        self._set_status("Connecting...", STYLE_STATUS_LOADING, "#FFA726")
        self._log(f"Connecting to {host}...")

        self._connection_worker = SSHConnectionWorker(
            host, username, password, NERFSTUDIO_SSH_PORT,
        )
        self._connection_worker.connected.connect(self._on_ssh_connected)
        self._connection_worker.connection_failed.connect(self._on_ssh_failed)
        self._connection_worker.start()

    def _on_ssh_connected(self, client):
        self._ssh_client = client
        self._is_connected = True
        self._connect_btn.setEnabled(True)
        self._connect_btn.setText("Disconnect")
        self._update_train_enabled()
        host = self._host_input.text().strip()
        self._set_status(f"Connected to {host}", STYLE_STATUS_CONNECTED, "#4CAF50")
        self._log("SSH connection established.")

    def _on_ssh_failed(self, error_msg: str):
        self._connect_btn.setEnabled(True)
        self._set_status(f"Failed: {error_msg}", STYLE_STATUS_ERROR, "#EF5350")
        self._log(f"Connection failed: {error_msg}")
        QMessageBox.warning(self, "SSH Connection Failed", error_msg)

    def _disconnect_ssh(self):
        self._stop_viewer()
        self._stop_current_training()
        if self._ssh_client:
            try:
                self._ssh_client.close()
            except Exception:
                pass
            self._ssh_client = None
        self._is_connected = False
        self._connect_btn.setText("Connect")
        set_button_enabled_style(self._train_btn, False)
        self._set_status("Disconnected", STYLE_STATUS_DISCONNECTED, "#6C6C80")
        self._log("Disconnected from server.")

    # ==================================================================
    # Training
    # ==================================================================

    def _on_start_training(self):
        if not self._ssh_client:
            QMessageBox.warning(self, "Not Connected", "Connect to the server first.")
            return

        train_folder = self._train_folder_input.text().strip()
        if not train_folder:
            QMessageBox.warning(self, "Missing Folder", "Enter a Nerfstudio folder name (for example: Cylinder or poster).")
            return
        if "/" in train_folder or "\\" in train_folder:
            QMessageBox.warning(self, "Invalid Folder", "Enter only the folder name, not a full path.")
            return

        set_button_enabled_style(self._train_btn, False)
        set_button_enabled_style(self._stop_train_btn, True)
        self._train_stage.setText("Initializing...")
        self._log(f"Starting training from data/nerfstudio/{train_folder}...")

        self._train_worker = NerfstudioTrainWorker(
            ssh_client=self._ssh_client,
            remote_job_path=NERFSTUDIO_WORKING_DIR,
            train_data_subdir=train_folder,
            nerfstudio_method="nerfacto",
            viewer_port=NERFSTUDIO_VIEWER_PORT,
            conda_env=NERFSTUDIO_CONDA_ENV,
            local_port=NERFSTUDIO_LOCAL_PORT,
        )
        self._train_worker.stage_changed.connect(self._on_train_stage_changed)
        self._train_worker.log_line.connect(self._on_train_log)
        self._train_worker.viewer_ready.connect(self._on_train_viewer_ready)
        self._train_worker.finished.connect(self._on_train_finished)
        self._train_worker.start()

    def _on_train_stage_changed(self, stage: str):
        labels = {
            "training": "Training NeRF model...",
            "complete": "Training complete!",
            "error": "Training failed.",
        }
        self._train_stage.setText(labels.get(stage, stage))

    def _on_train_log(self, line: str):
        self._log(line)

    def _on_train_finished(self, success: bool, error: str):
        # Training process exited — its embedded viewer is gone too
        self._cleanup_tunnel()
        self._stop_viewer()

        set_button_enabled_style(self._stop_train_btn, False)

        if success:
            self._train_stage.setText("Training complete!")
            self._log("Training completed successfully.")
        else:
            self._train_stage.setText(f"Failed: {error}")
            self._log(f"Training failed: {error}")
            if error and "Cancelled" not in error:
                QMessageBox.warning(self, "Training Failed", error)

        self._update_train_enabled()
        self._train_worker = None

    def _on_stop_training(self):
        self._log("Stopping training...")
        self._stop_current_training()

    def _stop_current_training(self):
        if self._train_worker and self._train_worker.isRunning():
            self._train_worker.request_stop()
            self._train_worker.wait(10000)
        self._train_worker = None
        self._cleanup_tunnel()
        set_button_enabled_style(self._stop_train_btn, False)

    # ==================================================================
    # Training → Viewer tunnel (live viewer during ns-train)
    # ==================================================================

    def _on_train_viewer_ready(self, url: str):
        """ns-train emitted a viewer URL — tunnel the port and load it."""
        try:
            self._setup_tunnel()
        except Exception as exc:
            self._log(f"Failed to set up SSH tunnel for training viewer: {exc}")
            return
        self._load_viewer(url)
        if self._health_checker and self._health_checker.isRunning():
            self._health_checker.request_stop()
            self._health_checker.wait(2000)
        self._health_checker = ViewerHealthChecker(
            url, interval_s=NERFSTUDIO_HEALTH_CHECK_INTERVAL_S,
        )
        self._health_checker.health_check_failed.connect(self._on_health_failed)
        self._health_checker.start()
        self._init_annotations()

    def _setup_tunnel(self):
        """SSH port forward: localhost:{LOCAL_PORT} -> remote:{VIEWER_PORT}."""
        self._cleanup_tunnel()  # tear down any prior tunnel first
        if not self._ssh_client:
            raise RuntimeError("SSH not connected.")
        transport = self._ssh_client.get_transport()
        if transport is None:
            raise RuntimeError("SSH transport is not active.")

        local_port = NERFSTUDIO_LOCAL_PORT
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", local_port))
        server.listen(128)
        server.settimeout(1.0)
        self._forward_server = server
        self._tunnel_stop = threading.Event()
        stop = self._tunnel_stop
        viewer_port = NERFSTUDIO_VIEWER_PORT

        def _forward_loop():
            while not stop.is_set():
                try:
                    client_sock, addr = server.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                try:
                    channel = transport.open_channel(
                        "direct-tcpip",
                        ("127.0.0.1", viewer_port),
                        addr,
                    )
                except Exception:
                    client_sock.close()
                    continue
                threading.Thread(
                    target=NerfstudioViewerWorker._relay,
                    args=(client_sock, channel),
                    daemon=True,
                ).start()

        threading.Thread(target=_forward_loop, daemon=True).start()
        self._log(f"SSH tunnel: localhost:{local_port} -> remote:{viewer_port}")

    def _cleanup_tunnel(self):
        """Tear down the training-viewer SSH tunnel."""
        if self._tunnel_stop is not None:
            self._tunnel_stop.set()
            self._tunnel_stop = None
        if self._forward_server is not None:
            try:
                self._forward_server.close()
            except Exception:
                pass
            self._forward_server = None

    # ==================================================================
    # Annotation Control
    # ==================================================================

    def _init_annotations(self):
        """Set up annotation tunnel and controller after viewer becomes ready."""
        if not self._ssh_client:
            self._log("Cannot init annotations: no SSH client.")
            return
        try:
            self._setup_annotation_tunnel()
        except Exception as exc:
            self._log(f"Failed to set up annotation tunnel: {exc}")
            return

        self._annotations_controller = AnnotationController(
            local_port=NERFSTUDIO_LOCAL_ANNOTATION_PORT,
            log_callback=self._log,
        )
        if self._annotations_controller.health_check():
            self._annotations_panel.set_controller(self._annotations_controller)
            self._annotations_btn.setIcon(self._make_circle_icon("#4CAF50"))
            self._annotations_btn.setEnabled(True)
            set_button_enabled_style(self._toggle_cams_btn, True)
            self._log("Annotations ready.")
        else:
            self._log("Annotation server not responding; annotations disabled.")
            self._annotations_controller = None

    def _cleanup_annotations(self):
        """Tear down annotation tunnel and controller."""
        self._annotations_controller = None
        self._annotations_btn.setIcon(self._make_circle_icon("#6C6C80"))
        self._annotations_btn.setEnabled(False)
        self._annotations_panel.set_controller(None)
        set_button_enabled_style(self._toggle_cams_btn, False)
        self._train_cams_visible = True
        self._cleanup_annotation_tunnel()

    def _setup_annotation_tunnel(self):
        """SSH port forward: localhost:{LOCAL_ANNOTATION_PORT} -> remote:{ANNOTATION_PORT}."""
        self._cleanup_annotation_tunnel()
        if not self._ssh_client:
            raise RuntimeError("SSH not connected.")
        transport = self._ssh_client.get_transport()
        if transport is None:
            raise RuntimeError("SSH transport is not active.")

        local_port = NERFSTUDIO_LOCAL_ANNOTATION_PORT
        remote_port = NERFSTUDIO_ANNOTATION_PORT

        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", local_port))
        server.listen(128)
        server.settimeout(1.0)
        self._annotation_tunnel_server = server
        self._annotation_tunnel_stop = threading.Event()
        stop = self._annotation_tunnel_stop

        def _forward_loop():
            while not stop.is_set():
                try:
                    client_sock, addr = server.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                try:
                    channel = transport.open_channel(
                        "direct-tcpip",
                        ("127.0.0.1", remote_port),
                        addr,
                    )
                except Exception:
                    client_sock.close()
                    continue
                threading.Thread(
                    target=NerfstudioViewerWorker._relay,
                    args=(client_sock, channel),
                    daemon=True,
                ).start()

        threading.Thread(target=_forward_loop, daemon=True).start()
        self._log(f"Annotation tunnel: localhost:{local_port} -> remote:{remote_port}")

    def _cleanup_annotation_tunnel(self):
        """Tear down the annotation SSH tunnel."""
        if self._annotation_tunnel_stop is not None:
            self._annotation_tunnel_stop.set()
            self._annotation_tunnel_stop = None
        if self._annotation_tunnel_server is not None:
            try:
                self._annotation_tunnel_server.close()
            except Exception:
                pass
            self._annotation_tunnel_server = None

    # ==================================================================
    # Toggle Training Camera Frustums
    # ==================================================================

    def _on_toggle_training_cams(self):
        """Toggle visibility of training camera frustums in the viewer."""
        if not self._annotations_controller:
            self._log("Cannot toggle cameras: no annotation controller.")
            return
        self._train_cams_visible = not self._train_cams_visible
        ok = self._annotations_controller.toggle_training_cameras(self._train_cams_visible)
        if ok:
            state = "visible" if self._train_cams_visible else "hidden"
            self._log(f"Training cameras: {state}")
        else:
            # Revert on failure
            self._train_cams_visible = not self._train_cams_visible
            self._log("Failed to toggle training cameras.")

    # ==================================================================
    # Viewer helpers
    # ==================================================================

    def _load_viewer(self, url: str):
        """Load the nerfstudio viewer URL into QWebEngineView."""
        self._viewer_url = url
        self._is_viewer_running = True
        set_button_enabled_style(self._reload_btn, True)
        self._viewer_status.setText(f"Running at {url}")
        self._viewer_status.setStyleSheet(STYLE_STATUS_CONNECTED)
        self._log(f"Viewer ready at {url}")

        if self._web_view:
            self._web_view.setUrl(QUrl(url))
            self._web_view.setVisible(True)
            self._placeholder.setVisible(False)

    def _stop_viewer(self):
        self._cleanup_annotations()

        if self._health_checker and self._health_checker.isRunning():
            self._health_checker.request_stop()
            self._health_checker.wait(2000)
        self._health_checker = None

        self._is_viewer_running = False
        self._viewer_url = None
        set_button_enabled_style(self._reload_btn, False)
        self._viewer_status.setText("Viewer: Not running")
        self._viewer_status.setStyleSheet(STYLE_STATUS_DISCONNECTED)
        self._show_placeholder()

    def _show_placeholder(self):
        if self._web_view:
            self._web_view.setVisible(False)
        self._placeholder.setText(
            "Connect to server and start training.\n"
            "Once a model is trained, click Launch Viewer to open\n"
            "the interactive 3D viewer here."
        )
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
    # Screenshot
    # ==================================================================

    def _on_screenshot(self):
        """Capture the Nerfstudio viewer, prompt for caption, and save."""
        if not self._web_view:
            self._log("Cannot screenshot: no web viewer available.")
            return
        if not self._export_dir:
            self._log("Cannot screenshot: no patient selected.")
            return

        self._export_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"
        filepath = self._export_dir / filename

        pixmap = self._web_view.grab()
        pixmap.save(str(filepath), "PNG")

        from PyQt6.QtWidgets import QInputDialog
        caption, ok = QInputDialog.getText(
            self, "Screenshot Caption",
            "Enter a caption for this screenshot:",
        )
        if not ok:
            caption = ""

        self._save_screenshot_caption(filename, caption)
        self._log(f"Screenshot saved: {filepath}")

    def _save_screenshot_caption(self, filename: str, caption: str):
        """Append or update caption for a screenshot in the patient's Export/screenshots.json."""
        import json

        if not self._export_dir:
            return
        meta_path = self._export_dir / "screenshots.json"
        data = {}
        if meta_path.exists():
            try:
                data = json.loads(meta_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                data = {}
        data[filename] = caption
        meta_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # ==================================================================
    # Cleanup (called by AppShell on logout / window close)
    # ==================================================================

    def cleanup(self):
        self._stop_viewer()
        self._stop_current_training()
        if self._ssh_client:
            try:
                self._ssh_client.close()
            except Exception:
                pass
            self._ssh_client = None
        self._is_connected = False
