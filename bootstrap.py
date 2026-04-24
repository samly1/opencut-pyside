from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtWidgets import QApplication

from app.controllers.app_controller import AppController
from app.ui.main_window import MainWindow
from app.ui.shared.theme import apply_basic_theme


@dataclass(slots=True)
class AppContext:
    app_controller: AppController


def build_app_context() -> AppContext:
    return AppContext(app_controller=AppController())


def create_application(argv: Sequence[str] | None = None) -> QApplication:
    existing_app = QApplication.instance()
    if existing_app is not None:
        return existing_app

    app = QApplication(list(argv) if argv is not None else [])
    app.setApplicationName("OpenCut PySide")
    app.setOrganizationName("OpenCut")
    apply_basic_theme(app)
    return app


def build_main_window(context: AppContext | None = None) -> MainWindow:
    resolved_context = context or build_app_context()
    return MainWindow(app_controller=resolved_context.app_controller)
