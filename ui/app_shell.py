from __future__ import annotations

from app.controllers.app_controller import AppController
from app.ui.inspector.inspector_panel import InspectorPanel
from app.ui.media_panel.media_panel import MediaPanel
from app.ui.preview.preview_widget import PreviewWidget
from app.ui.timeline.timeline_view import TimelineView
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSplitter, QVBoxLayout, QWidget


class AppShell(QWidget):
    """Main 4-panel editor shell for the MVP skeleton."""

    def __init__(self, app_controller: AppController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._app_controller = app_controller

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Top area: Media Panel | Preview | Inspector
        top_splitter = QSplitter(Qt.Orientation.Horizontal, self)
        top_splitter.addWidget(MediaPanel(self._app_controller.project_controller, self))
        top_splitter.addWidget(PreviewWidget(self._app_controller.playback_controller, self))
        top_splitter.addWidget(InspectorPanel(self._app_controller, self))
        top_splitter.setStretchFactor(0, 2)
        top_splitter.setStretchFactor(1, 5)
        top_splitter.setStretchFactor(2, 3)

        # Root: [Top area]
        #       -----------
        #       [Timeline]
        root_splitter = QSplitter(Qt.Orientation.Vertical, self)
        root_splitter.addWidget(top_splitter)

        self.timeline_view = TimelineView(
            self._app_controller.timeline_controller,
            self._app_controller.playback_controller,
            self._app_controller.selection_controller,
            self,
        )
        root_splitter.addWidget(self.timeline_view)

        # Give more space to the top area by default
        root_splitter.setStretchFactor(0, 4)
        root_splitter.setStretchFactor(1, 2)

        layout.addWidget(root_splitter)
