import sys
import os

# Ensure project root is on path when running from PyInstaller bundle
if getattr(sys, "frozen", False):
    sys.path.insert(0, sys._MEIPASS)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("ShareData")
    app.setOrganizationName("ShareData")

    # App icon
    base = os.path.dirname(os.path.abspath(__file__))
    if sys.platform == "darwin":
        icon_path = os.path.join(base, "assets", "icon.icns")
    elif sys.platform == "win32":
        icon_path = os.path.join(base, "assets", "icon.ico")
    else:
        icon_path = os.path.join(base, "assets", "icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # High-DPI support (Qt6 handles this automatically, but be explicit)
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
