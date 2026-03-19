import sys
from PyQt6.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QLabel,QLineEdit

app = QApplication(sys.argv)

window = QWidget()
window.setWindowTitle("Input Demo")

layout = QVBoxLayout()

input_box = QLineEdit()
input_box.setPlaceholderText("Type something here...")

label = QLabel("")
def show_text():
    label.setText(f"You typed:{input_box.text()}")

button = QPushButton("Submit")
button.clicked.connect(show_text)


layout.addWidget(input_box)
layout.addWidget(button)
layout.addWidget(label)
window.setLayout(layout)

window.show()
sys.exit(app.exec())