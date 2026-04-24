from __future__ import annotations

from app.controllers.app_controller import AppController
from app.domain.clips.audio_clip import AudioClip
from app.domain.clips.image_clip import ImageClip
from app.domain.clips.text_clip import TextClip
from app.domain.clips.video_clip import VideoClip
from app.ui.inspector.audio_inspector import AudioInspector
from app.ui.inspector.image_inspector import ImageInspector
from app.ui.inspector.project_inspector import ProjectInspector
from app.ui.inspector.text_inspector import TextInspector
from app.ui.inspector.video_inspector import VideoInspector
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class InspectorPanel(QWidget):
    def __init__(self, app_controller: AppController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._app_controller = app_controller
        self._project_inspector = ProjectInspector(self._app_controller.timeline_controller, self)
        self._clip_placeholder = QLabel("Select a clip to edit", self)
        self._clip_container = QWidget(self)
        self._clip_container_layout = QVBoxLayout(self._clip_container)
        self._clip_container_layout.setContentsMargins(0, 0, 0, 0)
        self._clip_container_layout.setSpacing(0)
        self._clip_widget: QWidget | None = None
        self._clip_widget_type: type[QWidget] | None = None

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        project_title = QLabel("Project", self)
        project_title.setStyleSheet("font-weight: 600;")
        layout.addWidget(project_title)
        layout.addWidget(self._project_inspector)

        clip_title = QLabel("Selected Clip", self)
        clip_title.setStyleSheet("font-weight: 600;")
        layout.addWidget(clip_title)
        self._clip_container_layout.addWidget(self._clip_placeholder)
        layout.addWidget(self._clip_container)
        layout.addStretch()

        self._app_controller.project_controller.project_changed.connect(self._refresh_project_inspector)
        self._app_controller.timeline_controller.timeline_edited.connect(self._refresh_from_state)
        self._app_controller.selection_controller.selection_changed.connect(self._refresh_from_state)

        self._refresh_from_state()

    def _refresh_from_state(self) -> None:
        self._refresh_project_inspector()
        self._refresh_clip_inspector()

    def _refresh_project_inspector(self) -> None:
        self._project_inspector.set_project(self._app_controller.project_controller.active_project())

    def _refresh_clip_inspector(self) -> None:
        project = self._app_controller.project_controller.active_project()
        clip = self._selected_clip(project)

        if clip is None:
            self._swap_clip_widget(None)
            return

        widget_type = self._widget_type_for_clip(clip)
        if self._clip_widget is not None and self._clip_widget_type is widget_type:
            setter = getattr(self._clip_widget, "set_clip", None)
            if callable(setter):
                setter(clip)
                return

        widget = widget_type(self._app_controller.timeline_controller, clip, self)
        self._swap_clip_widget(widget)

    def _swap_clip_widget(self, widget: QWidget | None) -> None:
        while self._clip_container_layout.count():
            item = self._clip_container_layout.takeAt(0)
            child = item.widget()
            if child is None:
                continue
            if child is not self._clip_placeholder:
                child.setParent(None)
                child.deleteLater()

        self._clip_widget = None
        self._clip_widget_type = None

        if widget is None:
            self._clip_placeholder.show()
            self._clip_container_layout.addWidget(self._clip_placeholder)
            return

        self._clip_placeholder.hide()
        self._clip_container_layout.addWidget(widget)
        self._clip_widget = widget
        self._clip_widget_type = type(widget)

    def _selected_clip(self, project) -> object | None:
        if project is None:
            return None

        selected_clip_id = self._app_controller.selection_controller.selected_clip_id()
        if selected_clip_id is None:
            return None

        for track in project.timeline.tracks:
            for clip in track.clips:
                if clip.clip_id == selected_clip_id:
                    return clip
        return None

    @staticmethod
    def _widget_type_for_clip(clip: object) -> type[QWidget]:
        if isinstance(clip, VideoClip):
            return VideoInspector
        if isinstance(clip, AudioClip):
            return AudioInspector
        if isinstance(clip, ImageClip):
            return ImageInspector
        if isinstance(clip, TextClip):
            return TextInspector
        return TextInspector
