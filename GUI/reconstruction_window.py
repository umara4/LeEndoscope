import os
import sys
import math
import struct
import zlib
import gzip
from pathlib import Path
import numpy as np
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QFrame, QMessageBox, QGridLayout, QStyle
)
from PyQt6.QtCore import Qt, QEvent, QSize

try:
    import importlib
    _lz4frame = importlib.import_module("lz4.frame")
    LZ4_AVAILABLE = True
except Exception:
    _lz4frame = None
    LZ4_AVAILABLE = False

try:
    import pyvista as pv
    from pyvistaqt import QtInteractor
    PYVISTA_AVAILABLE = True
except Exception:
    PYVISTA_AVAILABLE = False


class ReconstructionWindow(QMainWindow):
    SUPPORTED_FILTER = "3D Files (*.ply *.pcd *.obj *.stl *.off *.xyz);;All Files (*)"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("3D Reconstruction Viewer")
        self.resize(1100, 700)

        central = QWidget(self)
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        side_panel = QFrame(central)
        side_layout = QVBoxLayout(side_panel)
        side_layout.setContentsMargins(8, 8, 8, 8)
        side_layout.setSpacing(8)

        self.load_btn = QPushButton("Load Render", side_panel)
        self.load_btn.clicked.connect(self.on_load)
        side_layout.addWidget(self.load_btn)

        self.fit_btn = QPushButton("Fit View", side_panel)
        self.fit_btn.clicked.connect(self._fit_view)
        side_layout.addWidget(self.fit_btn)

        self.info_label = QLabel("No geometry loaded.", side_panel)
        self.info_label.setWordWrap(True)
        side_layout.addWidget(self.info_label)
        side_layout.addStretch(1)

        viewer_container = QWidget(central)
        viewer_layout = QVBoxLayout(viewer_container)
        viewer_layout.setContentsMargins(0, 0, 0, 0)

        self.placeholder = QLabel("PyVista interactive view not available.", viewer_container)
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.plotter = None
        if PYVISTA_AVAILABLE:
            try:
                self.plotter = QtInteractor(viewer_container)
                viewer_layout.addWidget(self.plotter, stretch=1)
                try:
                    self.plotter.show_axes()
                except Exception:
                    pass
            except Exception:
                self.plotter = None
                viewer_layout.addWidget(self.placeholder, stretch=1)
        else:
            viewer_layout.addWidget(self.placeholder, stretch=1)

        main_layout.addWidget(side_panel, stretch=1)
        main_layout.addWidget(viewer_container, stretch=4)

        self.mesh = None
        self._manip = None
        self.cam_center = (0.0, 0.0, 0.0)
        self.cam_dist = 1.0
        self.cam_az = 45.0
        self.cam_el = 30.0

        if not PYVISTA_AVAILABLE:
            QMessageBox.information(
                self,
                "Missing Dependency",
                "pyvista and pyvistaqt are required. Install with: pip install pyvista pyvistaqt vtk"
            )
            self.load_btn.setEnabled(False)
            self.fit_btn.setEnabled(False)
        else:
            self._create_manipulator()

    def _read_pcd(self, filename):
        with open(filename, "rb") as fh:
            header_lines = []
            while True:
                line = fh.readline()
                if not line:
                    break
                try:
                    s = line.decode("utf-8").strip()
                except Exception:
                    s = line.decode("latin-1").strip()
                header_lines.append(s)
                if s.lower().startswith("data"):
                    data_tokens = s.split()
                    data_type = data_tokens[1].lower() if len(data_tokens) > 1 else "binary"
                    break

            def _get(prefix):
                for ln in header_lines:
                    if ln.lower().startswith(prefix):
                        return ln.split()[1:]
                return None

            fields = _get("fields") or _get("field")
            size = _get("size")
            types = _get("type")
            count = _get("count")
            points_tok = _get("points")
            width_tok = _get("width")
            height_tok = _get("height")

            num_points = None
            if points_tok:
                try:
                    num_points = int(points_tok[0])
                except Exception:
                    num_points = None
            else:
                try:
                    w = int(width_tok[0]) if width_tok else 0
                    h = int(height_tok[0]) if height_tok else 0
                    num_points = w * h if (w and h) else None
                except Exception:
                    num_points = None

            if data_type == "ascii":
                rest = fh.read().decode("utf-8", errors="ignore").splitlines()
                pts = []
                fields_l = [f.lower() for f in fields] if fields else []
                try:
                    x_i = fields_l.index("x") if "x" in fields_l else 0
                    y_i = fields_l.index("y") if "y" in fields_l else 1
                    z_i = fields_l.index("z") if "z" in fields_l else 2
                except Exception:
                    x_i, y_i, z_i = 0, 1, 2
                for row in rest:
                    row = row.strip()
                    if not row or row.startswith("#"):
                        continue
                    parts = row.split()
                    if len(parts) <= max(x_i, y_i, z_i):
                        continue
                    try:
                        x = float(parts[x_i])
                        y = float(parts[y_i])
                        z = float(parts[z_i])
                    except Exception:
                        continue
                    pts.append((x, y, z))
                if not pts:
                    raise ValueError("No points parsed from ASCII PCD.")
                return pv.PolyData(np.asarray(pts, dtype=float))

            raw = None
            uncomp_size = None
            if data_type.startswith("binary_compressed"):
                hdr = fh.read(8)
                if len(hdr) != 8:
                    raise ValueError("Invalid binary_compressed PCD header.")
                comp_size, uncomp_size = struct.unpack("<II", hdr)
                comp = fh.read(int(comp_size))
                if len(comp) != int(comp_size):
                    raise ValueError("Unexpected EOF reading compressed payload.")

                decompressed = None
                try:
                    decompressed = zlib.decompress(comp)
                except Exception:
                    pass
                if decompressed is None:
                    try:
                        decompressed = gzip.decompress(comp)
                    except Exception:
                        pass
                if decompressed is None and LZ4_AVAILABLE:
                    try:
                        decompressed = _lz4frame.decompress(comp)
                    except Exception:
                        pass
                if decompressed is None:
                    try:
                        decompressed = zlib.decompress(comp, wbits=-zlib.MAX_WBITS)
                    except Exception:
                        pass
                if decompressed is None:
                    raise ValueError("Failed to decompress binary_compressed PCD payload.")
                raw = decompressed

            if data_type.startswith("binary"):
                if not (fields and size and types):
                    raise ValueError("Incomplete PCD header for binary parsing.")
                sizes = [int(x) for x in size]
                types_l = [t.upper() for t in types]
                counts = [int(c) for c in count] if count else [1] * len(fields)
                bytes_per_point = sum(sizes[i] * counts[i] for i in range(len(sizes)))
                if num_points is None:
                    if uncomp_size:
                        num_points = int(uncomp_size) // bytes_per_point
                    else:
                        cur = fh.tell()
                        fh.seek(0, os.SEEK_END)
                        total = fh.tell()
                        data_size = total - cur
                        fh.seek(cur, os.SEEK_SET)
                        num_points = max(0, data_size // bytes_per_point)
                expected = int(num_points * bytes_per_point)
                if raw is None:
                    raw = fh.read(expected)
                if len(raw) < expected:
                    avail = len(raw) // bytes_per_point
                    if avail == 0:
                        raise ValueError("No binary point data available.")
                    raw = raw[: avail * bytes_per_point]
                    num_points = avail

                dtype_elems = []
                for i, fname in enumerate(fields):
                    fsize = sizes[i]
                    ftype = types_l[i]
                    fcount = counts[i]
                    if ftype == "F":
                        base = "<f4" if fsize == 4 else "<f8"
                    elif ftype == "I":
                        base = {1: "<i1", 2: "<i2", 4: "<i4", 8: "<i8"}[fsize]
                    elif ftype == "U":
                        base = {1: "<u1", 2: "<u2", 4: "<u4", 8: "<u8"}[fsize]
                    else:
                        raise ValueError(f"Unsupported PCD field type: {ftype}")
                    if fcount == 1:
                        dtype_elems.append((fname, base))
                    else:
                        dtype_elems.append((fname, base, (fcount,)))

                structured = np.frombuffer(raw, dtype=np.dtype(dtype_elems))
                fields_l = [f.lower() for f in fields]
                try:
                    xi = fields_l.index("x")
                    yi = fields_l.index("y")
                    zi = fields_l.index("z")
                except ValueError:
                    xi, yi, zi = 0, 1, 2
                names = structured.dtype.names

                def _get_arr(name):
                    if name in names:
                        arr = structured[name]
                    else:
                        if isinstance(name, (bytes, bytearray)):
                            arr = structured[name.decode()]
                        else:
                            raise ValueError(f"Missing field {name}")
                    if getattr(arr, "ndim", 0) == 2:
                        arr = arr[:, 0]
                    return np.asarray(arr)

                def _to_float(a):
                    a = np.asarray(a)
                    if a.dtype.kind in ("i", "u", "f"):
                        return a.astype(float)
                    if a.dtype.kind in ("S", "U"):
                        out = []
                        for v in a:
                            try:
                                sv = v.decode() if isinstance(v, (bytes, bytearray)) else str(v)
                                out.append(float(sv))
                            except Exception:
                                out.append(np.nan)
                        return np.array(out, dtype=float)
                    out = []
                    for v in a:
                        try:
                            out.append(float(v))
                        except Exception:
                            try:
                                vv = np.asarray(v)
                                out.append(float(vv.ravel()[0]))
                            except Exception:
                                out.append(np.nan)
                    return np.array(out, dtype=float)

                x = _get_arr(fields[xi])
                y = _get_arr(fields[yi])
                z = _get_arr(fields[zi])

                x_f = _to_float(x)
                y_f = _to_float(y)
                z_f = _to_float(z)

                mask = np.isfinite(x_f) & np.isfinite(y_f) & np.isfinite(z_f)
                pts = np.vstack((x_f[mask], y_f[mask], z_f[mask])).T
                return pv.PolyData(pts)

            raise ValueError(f"Unsupported PCD DATA type: {data_type}")

    def on_load(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Load Render", str(Path.home()), self.SUPPORTED_FILTER)
        if not fname:
            return
        try:
            ext = Path(fname).suffix.lower()
            if ext == ".pcd":
                mesh = self._read_pcd(fname)
            else:
                mesh = pv.read(fname)
                mesh = pv.wrap(mesh)
        except Exception as e:
            QMessageBox.warning(self, "Load Error", f"Failed to read file:\n{e}")
            return

        if mesh is None or getattr(mesh, "n_points", 0) == 0:
            QMessageBox.warning(self, "Empty Geometry", "Loaded geometry is empty.")
            return

        self.mesh = mesh
        self._display_mesh(mesh)
        self.info_label.setText(
            f"Loaded: {os.path.basename(fname)} — points: {mesh.n_points}, faces: {getattr(mesh, 'n_faces', 0)}"
        )

    def _display_mesh(self, mesh):
        if self.plotter is None:
            return
        try:
            self.plotter.clear()
            self.plotter.remove_actor("*")
        except Exception:
            pass

        try:
            # If mesh has faces, render as mesh
            if getattr(mesh, "n_faces", 0) > 0:
                if "RGB" in mesh.point_data:
                    self.plotter.add_mesh(mesh, scalars="RGB", rgb=True)
                else:
                    self.plotter.add_mesh(mesh, show_edges=False, smooth_shading=True)
            else:
                # Point cloud case
                if "RGB" in mesh.point_data:
                    self.plotter.add_points(mesh, scalars="RGB", rgb=True, point_size=5)
                else:
                    self.plotter.add_points(mesh.points, point_size=3)

            self.plotter.reset_camera()
            self.plotter.render()
        except Exception as ex:
            QMessageBox.warning(self, "Render Error", f"Failed to render mesh:\n{ex}")



    def _create_manipulator(self):
        if self.plotter is None:
            return
        interactor = self.plotter.interactor

        # Transparent overlay frame
        self._manip = QFrame(interactor)
        self._manip.setObjectName("manipulator")
        self._manip.setStyleSheet("""
            #manipulator {
                background: rgba(255,255,255,0.0);  /* fully transparent */
            }
        """)
        self._manip.setFixedSize(QSize(140, 140))
        grid = QGridLayout(self._manip)
        grid.setContentsMargins(8, 8, 8, 8)

        # Arrow buttons using system icons
        btn_up = QPushButton()
        btn_up.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowUp))
        btn_down = QPushButton()
        btn_down.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown))
        btn_left = QPushButton()
        btn_left.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowLeft))
        btn_right = QPushButton()
        btn_right.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowRight))

        # Axis control button in the centre
        btn_center = QPushButton("XYZ")  # placeholder text
        # Later you can replace with a small axis widget or icon

        for b in (btn_up, btn_down, btn_left, btn_right, btn_center):
            b.setFixedSize(36, 36)
            b.setStyleSheet("background: rgba(255,255,255,0.6); border-radius: 18px;")

        grid.addWidget(btn_up, 0, 1)
        grid.addWidget(btn_left, 1, 0)
        grid.addWidget(btn_center, 1, 1)
        grid.addWidget(btn_right, 1, 2)
        grid.addWidget(btn_down, 2, 1)

        # Connect buttons to orbit/fit
        btn_left.clicked.connect(lambda: self._orbit(delta_az=-15))
        btn_right.clicked.connect(lambda: self._orbit(delta_az=15))
        btn_up.clicked.connect(lambda: self._orbit(delta_el=10))
        btn_down.clicked.connect(lambda: self._orbit(delta_el=-10))
        btn_center.clicked.connect(self._fit_view)

        self._manip.raise_()
        interactor.installEventFilter(self)
        self._position_manip()

    def eventFilter(self, watched, event):
        if self.plotter is not None and watched is self.plotter.interactor and event.type() == QEvent.Type.Resize:
            self._position_manip()
        return super().eventFilter(watched, event)

    def _position_manip(self):
        if self.plotter is None or self._manip is None:
            return
        pw = self.plotter.interactor.width()
        ph = self.plotter.interactor.height()
        mw = self._manip.width()
        mh = self._manip.height()
        margin = 12
        x = max(0, pw - mw - margin)
        y = max(0, ph - mh - margin)
        self._manip.move(x, y)

    def _orbit(self, delta_az=0.0, delta_el=0.0):
        self.cam_az = (self.cam_az + delta_az) % 360.0
        self.cam_el = max(-89.0, min(89.0, self.cam_el + delta_el))
        self._apply_camera()

    def _fit_view(self):
        if self.mesh is None:
            self.cam_center = (0.0, 0.0, 0.0)
            self.cam_dist = 1.0
        else:
            try:
                bounds = self.mesh.bounds
                span = max(bounds[1]-bounds[0], bounds[3]-bounds[2], bounds[5]-bounds[4])
                self.cam_dist = max(1e-6, span * 1.5)
                self.cam_center = (
                    0.5*(bounds[0]+bounds[1]),
                    0.5*(bounds[2]+bounds[3]),
                    0.5*(bounds[4]+bounds[5])
                )
            except Exception:
                self.cam_center = (0.0, 0.0, 0.0)
                self.cam_dist = 1.0
        self.cam_az = 45.0
        self.cam_el = 30.0
        self._apply_camera()

    def _apply_camera(self):
        if self.plotter is None:
            return
        az_r = math.radians(self.cam_az)
        el_r = math.radians(self.cam_el)
        r = max(1e-6, float(self.cam_dist))
        cx, cy, cz = self.cam_center
        cam_x = cx + r * math.cos(el_r) * math.cos(az_r)
        cam_y = cy + r * math.cos(el_r) * math.sin(az_r)
        cam_z = cz + r * math.sin(el_r)
        try:
            self.plotter.camera_position = [(cam_x, cam_y, cam_z), tuple(self.cam_center), (0, 0, 1)]
            self.plotter.render()
        except Exception:
            try:
                self.plotter.camera.position = (cam_x, cam_y, cam_z)
                self.plotter.camera.focal_point = tuple(self.cam_center)
                self.plotter.camera.up = (0, 0, 1)
                self.plotter.render()
            except Exception:
                pass


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = ReconstructionWindow()
    w.show()
    sys.exit(app.exec())

    