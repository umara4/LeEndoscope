from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QWidget
from pyvistaqt import QtInteractor
import pyvista as pv

class ReconstructionWindow(QMainWindow):
    def __init__(self, ply_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("3D Reconstruction Viewer")
        self.resize(800, 600)

        # Central widget
        central = QWidget()
        layout = QVBoxLayout(central)
        self.setCentralWidget(central)

        # PyVista interactor
        self.plotter = QtInteractor(self)
        layout.addWidget(self.plotter.interactor)

        try:
            # Load point cloud or mesh
            geom = pv.read(ply_path)

            # Clear previous scene
            self.plotter.clear()

            # If it's a point cloud with RGB values
            if hasattr(geom, "point_data") and "RGB" in geom.point_data:
                self.plotter.add_points(geom, scalars="RGB", rgb=True, point_size=3)
            else:
                # If it's a mesh, just render with its stored colours
                self.plotter.add_mesh(geom, scalars=None)

            self.plotter.show()
        except Exception as e:
            print("Error loading point cloud:", e)