from __future__ import annotations

from PySide6.QtWidgets import QApplication


def apply_basic_theme(app: QApplication) -> None:
    app.setStyleSheet(
        """
        QWidget {
            font-family: "Segoe UI";
            font-size: 10pt;
        }
        QMainWindow {
            background-color: #f3f5f7;
        }
        #preview_canvas {
            background-color: #dfe5ec;
            border: 1px solid #b7c2ce;
            border-radius: 4px;
            color: #243447;
            font-weight: 600;
        }
        """
    )
