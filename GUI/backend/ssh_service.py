"""
SSH service for remote Nerfstudio viewer management.

Provides QThread workers for:
- SSH connection (SSHConnectionWorker)
- Nerfstudio viewer launch + SSH port forwarding (NerfstudioViewerWorker)
- Viewer health monitoring (ViewerHealthChecker)

All workers follow the ArduinoFlasher pattern: pyqtSignal for output,
threading.Event for cooperative shutdown.
"""
from __future__ import annotations

import re
import socket
import threading
import time
import urllib.request

from PyQt6.QtCore import QThread, pyqtSignal

try:
    import paramiko
    PARAMIKO_AVAILABLE = True
except ImportError:
    paramiko = None
    PARAMIKO_AVAILABLE = False

from shared.constants import (
    NERFSTUDIO_WORKING_DIR,
    NERFSTUDIO_CONDA_ENV,
    NERFSTUDIO_VIEWER_STARTUP_TIMEOUT_S,
)

# Regex to detect the viewer URL in ns-viewer stdout
_URL_RE = re.compile(r"https?://[\w.-]+:\d+")
# Strip ANSI escape sequences (PTY output includes colors/formatting)
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]|\x1b\].*?\x07")


class SSHConnectionWorker(QThread):
    """Establishes an SSH connection in a background thread."""

    connected = pyqtSignal(object)       # paramiko.SSHClient
    connection_failed = pyqtSignal(str)  # error message

    def __init__(self, host: str, username: str, password: str, port: int = 22):
        super().__init__()
        self._host = host
        self._username = username
        self._password = password
        self._port = port

    def run(self):
        if not PARAMIKO_AVAILABLE:
            self.connection_failed.emit(
                "paramiko is not installed. Run: pip install paramiko"
            )
            return
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                self._host,
                port=self._port,
                username=self._username,
                password=self._password,
                timeout=15,
                allow_agent=False,
                look_for_keys=False,
            )
            transport = client.get_transport()
            if transport:
                transport.set_keepalive(30)
            self.connected.emit(client)
        except paramiko.AuthenticationException:
            self.connection_failed.emit("Authentication failed -- check password.")
        except socket.timeout:
            self.connection_failed.emit(
                f"Connection timed out reaching {self._host}:{self._port}."
            )
        except Exception as exc:
            self.connection_failed.emit(str(exc))


class NerfstudioViewerWorker(QThread):
    """Launches ns-viewer on the remote server via SSH and sets up port forwarding.

    Follows the ArduinoFlasher pattern: real-time output_line signals,
    cooperative shutdown via threading.Event + request_stop().
    """

    output_line = pyqtSignal(str)
    viewer_ready = pyqtSignal(str)    # local URL (http://localhost:{port})
    viewer_failed = pyqtSignal(str)
    viewer_stopped = pyqtSignal()

    def __init__(
        self,
        ssh_client,
        config_path: str,
        remote_host: str,
        local_port: int = 7007,
        viewer_port: int = 7007,
    ):
        super().__init__()
        self._client = ssh_client
        self._config_path = config_path
        self._remote_host = remote_host
        self._local_port = local_port
        self._viewer_port = viewer_port
        self._stop_event = threading.Event()
        self._channel = None
        self._forward_server: socket.socket | None = None

    def request_stop(self):
        """Signal the worker to shut down cooperatively."""
        self._stop_event.set()

    # ------------------------------------------------------------------
    # Port forwarding
    # ------------------------------------------------------------------

    def _find_available_local_port(self) -> int:
        """Try self._local_port first, then fall back to +1 .. +13."""
        for offset in range(14):
            port = self._local_port + offset
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.bind(("127.0.0.1", port))
                sock.close()
                return port
            except OSError:
                continue
        raise OSError("No available local port in range 7007-7020.")

    def _setup_port_forward(self, local_port: int):
        """Create a local listening socket that tunnels to the remote viewer port."""
        transport = self._client.get_transport()
        if transport is None:
            raise RuntimeError("SSH transport is not active.")

        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", local_port))
        server.listen(128)
        server.settimeout(1.0)
        self._forward_server = server

        def _forward_loop():
            while not self._stop_event.is_set():
                try:
                    client_sock, addr = server.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                try:
                    channel = transport.open_channel(
                        "direct-tcpip",
                        ("127.0.0.1", self._viewer_port),
                        addr,
                    )
                except Exception:
                    client_sock.close()
                    continue
                threading.Thread(
                    target=self._relay, args=(client_sock, channel), daemon=True
                ).start()

        threading.Thread(target=_forward_loop, daemon=True).start()

    @staticmethod
    def _relay(sock: socket.socket, channel):
        """Bidirectional relay using two threads — one per direction."""
        def _remote_to_local():
            try:
                while True:
                    data = channel.recv(65536)
                    if not data:
                        break
                    sock.sendall(data)
            except Exception:
                pass
            finally:
                try:
                    sock.shutdown(socket.SHUT_WR)
                except Exception:
                    pass

        def _local_to_remote():
            try:
                while True:
                    data = sock.recv(65536)
                    if not data:
                        break
                    channel.sendall(data)
            except Exception:
                pass
            finally:
                try:
                    channel.shutdown(2)
                except Exception:
                    pass

        t = threading.Thread(target=_remote_to_local, daemon=True)
        t.start()
        _local_to_remote()  # run in current thread
        t.join(timeout=5)
        try:
            sock.close()
        except Exception:
            pass
        try:
            channel.close()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Main run
    # ------------------------------------------------------------------

    def run(self):
        # 1. Find an available local port
        try:
            local_port = self._find_available_local_port()
        except OSError as exc:
            self.viewer_failed.emit(str(exc))
            return

        if local_port != self._local_port:
            self.output_line.emit(
                f"Port {self._local_port} in use; using {local_port} instead."
            )

        # 2. Set up SSH port forward
        try:
            self._setup_port_forward(local_port)
            self.output_line.emit(
                f"SSH tunnel: localhost:{local_port} -> remote:{self._viewer_port}"
            )
        except Exception as exc:
            self.viewer_failed.emit(f"Port forwarding failed: {exc}")
            return

        # 3. Execute ns-viewer on the remote host
        config = self._config_path.rstrip("/")
        if not config.endswith((".yml", ".yaml")):
            config = config + "/config.yml"
        cmd = (
            f'bash -lc "'
            f"cd {NERFSTUDIO_WORKING_DIR} && "
            f"conda activate {NERFSTUDIO_CONDA_ENV} && "
            f"ns-viewer --load-config {config} "
            f"--viewer.websocket-port {self._viewer_port}"
            f'"'
        )
        self.output_line.emit(f"Running: {cmd}")

        try:
            transport = self._client.get_transport()
            if transport is None:
                self.viewer_failed.emit("SSH transport is not active.")
                return
            self._channel = transport.open_session()
            self._channel.get_pty()
            self._channel.exec_command(cmd)
        except Exception as exc:
            self.viewer_failed.emit(f"Failed to execute remote command: {exc}")
            self._cleanup()
            return

        # 4. Monitor stdout for viewer URL
        viewer_url = None
        _signalled = False
        start_time = time.time()
        buf = ""

        try:
            while not self._stop_event.is_set():
                # Check timeout
                elapsed = time.time() - start_time
                if viewer_url is None and elapsed > NERFSTUDIO_VIEWER_STARTUP_TIMEOUT_S:
                    _signalled = True
                    self.viewer_failed.emit(
                        f"Viewer did not start within {NERFSTUDIO_VIEWER_STARTUP_TIMEOUT_S}s."
                    )
                    return

                # Check if remote process exited
                if self._channel.exit_status_ready():
                    code = self._channel.recv_exit_status()
                    # Drain remaining output (including partial buf)
                    while self._channel.recv_ready():
                        buf += self._channel.recv(4096).decode("utf-8", errors="replace")
                    # Flush everything left in buf
                    for leftover in buf.splitlines():
                        leftover = _ANSI_RE.sub("", leftover).strip()
                        if leftover:
                            self.output_line.emit(leftover)
                    buf = ""
                    _signalled = True
                    if viewer_url is None:
                        self.viewer_failed.emit(
                            f"ns-viewer exited with code {code} before becoming ready."
                        )
                    else:
                        self.output_line.emit(f"ns-viewer exited with code {code}.")
                        self.viewer_stopped.emit()
                    return

                # Read available stdout
                if self._channel.recv_ready():
                    chunk = self._channel.recv(4096).decode("utf-8", errors="replace")
                    buf += chunk
                    while "\n" in buf:
                        line, buf = buf.split("\n", 1)
                        line = line.rstrip("\r")
                        clean = _ANSI_RE.sub("", line)
                        self.output_line.emit(clean)
                        # Detect viewer URL
                        if viewer_url is None:
                            match = _URL_RE.search(clean)
                            if match:
                                viewer_url = f"http://localhost:{local_port}"
                                self.output_line.emit(
                                    f"Viewer detected! Forwarding to {viewer_url}"
                                )
                                self.viewer_ready.emit(viewer_url)

                time.sleep(0.05)
        except Exception as exc:
            _signalled = True
            self.viewer_failed.emit(f"Error monitoring viewer: {exc}")
        finally:
            self._cleanup()
            if not self._stop_event.is_set() and not _signalled:
                self.viewer_stopped.emit()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def _cleanup(self):
        """Terminate remote process, close port forward, close channel."""
        # Send Ctrl-C to remote process
        if self._channel is not None:
            try:
                if not self._channel.closed:
                    self._channel.send("\x03")  # Ctrl-C
                    time.sleep(0.5)
                    if not self._channel.exit_status_ready():
                        self._channel.send("exit\n")
                        time.sleep(0.5)
                    self._channel.close()
            except Exception:
                pass
            self._channel = None

        # Close port forwarding server
        if self._forward_server is not None:
            try:
                self._forward_server.close()
            except Exception:
                pass
            self._forward_server = None


class ViewerHealthChecker(QThread):
    """Periodically pings the viewer URL to check it is still responsive."""

    health_ok = pyqtSignal()
    health_check_failed = pyqtSignal(str)

    def __init__(self, url: str, interval_s: float = 15.0):
        super().__init__()
        self._url = url
        self._interval = interval_s
        self._stop_event = threading.Event()

    def request_stop(self):
        self._stop_event.set()

    def run(self):
        consecutive_failures = 0
        while not self._stop_event.is_set():
            self._stop_event.wait(self._interval)
            if self._stop_event.is_set():
                break
            try:
                urllib.request.urlopen(self._url, timeout=5)
                consecutive_failures = 0
                self.health_ok.emit()
            except Exception as exc:
                consecutive_failures += 1
                if consecutive_failures >= 3:
                    self.health_check_failed.emit(
                        f"Viewer unreachable ({consecutive_failures} checks): {exc}"
                    )
