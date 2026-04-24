from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.controllers.app_controller import AppController
from app.domain.clips.audio_clip import AudioClip
from app.domain.clips.base_clip import BaseClip
from app.domain.clips.image_clip import ImageClip
from app.domain.clips.text_clip import TextClip
from app.domain.clips.video_clip import VideoClip


class InspectorPanel(QWidget):
    def __init__(self, app_controller: AppController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._app_controller = app_controller
        self._updating_from_model = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self._header_label = QLabel("Inspector")
        self._header_label.setStyleSheet("font-weight: bold; font-size: 11pt;")
        layout.addWidget(self._header_label)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._scroll_content = QWidget()
        self._scroll_layout = QVBoxLayout(self._scroll_content)
        self._scroll_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._no_selection_label = QLabel("No clip selected")
        self._no_selection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._scroll_layout.addWidget(self._no_selection_label)

        self._clip_group = QGroupBox("Clip Properties")
        clip_form = QFormLayout(self._clip_group)

        self._name_edit = QLineEdit()
        self._name_edit.editingFinished.connect(self._on_name_changed)
        clip_form.addRow("Name:", self._name_edit)

        self._start_spin = QDoubleSpinBox()
        self._start_spin.setDecimals(3)
        self._start_spin.setRange(0.0, 99999.0)
        self._start_spin.setSuffix(" s")
        self._start_spin.valueChanged.connect(self._on_start_changed)
        clip_form.addRow("Start:", self._start_spin)

        self._duration_spin = QDoubleSpinBox()
        self._duration_spin.setDecimals(3)
        self._duration_spin.setRange(0.001, 99999.0)
        self._duration_spin.setSuffix(" s")
        self._duration_spin.valueChanged.connect(self._on_duration_changed)
        clip_form.addRow("Duration:", self._duration_spin)

        self._opacity_spin = QDoubleSpinBox()
        self._opacity_spin.setDecimals(2)
        self._opacity_spin.setRange(0.0, 1.0)
        self._opacity_spin.setSingleStep(0.05)
        self._opacity_spin.valueChanged.connect(self._on_opacity_changed)
        clip_form.addRow("Opacity:", self._opacity_spin)

        self._scroll_layout.addWidget(self._clip_group)
        self._clip_group.hide()

        self._type_specific_group = QGroupBox("Type Properties")
        self._type_specific_form = QFormLayout(self._type_specific_group)

        self._speed_spin = QDoubleSpinBox()
        self._speed_spin.setDecimals(2)
        self._speed_spin.setRange(0.01, 100.0)
        self._speed_spin.setSingleStep(0.25)
        self._speed_spin.setSuffix("x")
        self._speed_spin.valueChanged.connect(self._on_speed_changed)

        self._gain_spin = QDoubleSpinBox()
        self._gain_spin.setDecimals(1)
        self._gain_spin.setRange(-60.0, 24.0)
        self._gain_spin.setSuffix(" dB")
        self._gain_spin.valueChanged.connect(self._on_gain_changed)

        self._scale_spin = QDoubleSpinBox()
        self._scale_spin.setDecimals(2)
        self._scale_spin.setRange(0.01, 100.0)
        self._scale_spin.setSingleStep(0.1)
        self._scale_spin.valueChanged.connect(self._on_scale_changed)

        self._content_edit = QLineEdit()
        self._content_edit.editingFinished.connect(self._on_content_changed)

        self._scroll_layout.addWidget(self._type_specific_group)
        self._type_specific_group.hide()

        self._scroll_layout.addStretch()
        scroll_area.setWidget(self._scroll_content)
        layout.addWidget(scroll_area)

        self._app_controller.selection_controller.selection_changed.connect(self._refresh)
        self._app_controller.timeline_controller.timeline_changed.connect(self._refresh)
        self._refresh()

    def _selected_clip(self) -> BaseClip | None:
        clip_id = self._app_controller.selection_controller.selected_clip_id()
        if clip_id is None:
            return None
        timeline = self._app_controller.timeline_controller.active_timeline()
        if timeline is None:
            return None
        for track in timeline.tracks:
            for clip in track.clips:
                if clip.clip_id == clip_id:
                    return clip
        return None

    def _refresh(self) -> None:
        clip = self._selected_clip()
        if clip is None:
            self._no_selection_label.show()
            self._clip_group.hide()
            self._type_specific_group.hide()
            return

        self._no_selection_label.hide()
        self._clip_group.show()

        self._updating_from_model = True

        self._name_edit.setText(clip.name)
        self._start_spin.setValue(clip.timeline_start)
        self._duration_spin.setValue(clip.duration)
        self._opacity_spin.setValue(clip.opacity)

        self._setup_type_specific_fields(clip)

        self._updating_from_model = False

    def _setup_type_specific_fields(self, clip: BaseClip) -> None:
        while self._type_specific_form.rowCount() > 0:
            self._type_specific_form.removeRow(0)

        if isinstance(clip, VideoClip):
            self._speed_spin.setValue(clip.playback_speed)
            self._type_specific_form.addRow("Speed:", self._speed_spin)
            self._type_specific_group.setTitle("Video Properties")
            self._type_specific_group.show()
        elif isinstance(clip, AudioClip):
            self._gain_spin.setValue(clip.gain_db)
            self._type_specific_form.addRow("Gain:", self._gain_spin)
            self._type_specific_group.setTitle("Audio Properties")
            self._type_specific_group.show()
        elif isinstance(clip, ImageClip):
            self._scale_spin.setValue(clip.scale)
            self._type_specific_form.addRow("Scale:", self._scale_spin)
            self._type_specific_group.setTitle("Image Properties")
            self._type_specific_group.show()
        elif isinstance(clip, TextClip):
            self._content_edit.setText(clip.content)
            self._type_specific_form.addRow("Content:", self._content_edit)
            self._type_specific_group.setTitle("Text Properties")
            self._type_specific_group.show()
        else:
            self._type_specific_group.hide()

    def _on_name_changed(self) -> None:
        if self._updating_from_model:
            return
        clip = self._selected_clip()
        if clip is None:
            return
        new_name = self._name_edit.text().strip()
        if new_name and new_name != clip.name:
            self._app_controller.inspector_controller.update_clip_property(clip, "name", new_name)

    def _on_start_changed(self, value: float) -> None:
        if self._updating_from_model:
            return
        clip = self._selected_clip()
        if clip is None:
            return
        if abs(value - clip.timeline_start) > 1e-6:
            self._app_controller.inspector_controller.update_clip_property(clip, "timeline_start", value)

    def _on_duration_changed(self, value: float) -> None:
        if self._updating_from_model:
            return
        clip = self._selected_clip()
        if clip is None:
            return
        if abs(value - clip.duration) > 1e-6:
            self._app_controller.inspector_controller.update_clip_property(clip, "duration", value)

    def _on_opacity_changed(self, value: float) -> None:
        if self._updating_from_model:
            return
        clip = self._selected_clip()
        if clip is None:
            return
        if abs(value - clip.opacity) > 1e-6:
            self._app_controller.inspector_controller.update_clip_property(clip, "opacity", value)

    def _on_speed_changed(self, value: float) -> None:
        if self._updating_from_model:
            return
        clip = self._selected_clip()
        if clip is None or not isinstance(clip, VideoClip):
            return
        if abs(value - clip.playback_speed) > 1e-6:
            self._app_controller.inspector_controller.update_clip_property(clip, "playback_speed", value)

    def _on_gain_changed(self, value: float) -> None:
        if self._updating_from_model:
            return
        clip = self._selected_clip()
        if clip is None or not isinstance(clip, AudioClip):
            return
        if abs(value - clip.gain_db) > 0.05:
            self._app_controller.inspector_controller.update_clip_property(clip, "gain_db", value)

    def _on_scale_changed(self, value: float) -> None:
        if self._updating_from_model:
            return
        clip = self._selected_clip()
        if clip is None or not isinstance(clip, ImageClip):
            return
        if abs(value - clip.scale) > 1e-6:
            self._app_controller.inspector_controller.update_clip_property(clip, "scale", value)

    def _on_content_changed(self) -> None:
        if self._updating_from_model:
            return
        clip = self._selected_clip()
        if clip is None or not isinstance(clip, TextClip):
            return
        new_content = self._content_edit.text()
        if new_content != clip.content:
            self._app_controller.inspector_controller.update_clip_property(clip, "content", new_content)
