from __future__ import annotations

from app.domain.clips.video_clip import VideoClip
from app.ui.inspector._clip_inspector_base import ClipInspectorBase, block_signals
from PySide6.QtWidgets import QDoubleSpinBox


class VideoInspector(ClipInspectorBase):
    def __init__(self, timeline_controller: object, clip: VideoClip, parent=None) -> None:
        super().__init__(timeline_controller, clip, parent)

    def _build_specific_fields(self) -> None:
        self._playback_speed_spin = QDoubleSpinBox(self)
        self._playback_speed_spin.setRange(0.1, 8.0)
        self._playback_speed_spin.setDecimals(2)
        self._playback_speed_spin.setSingleStep(0.1)
        self._playback_speed_spin.setKeyboardTracking(False)
        self._playback_speed_spin.editingFinished.connect(self._commit_specific_fields)
        self._form.addRow("Playback Speed", self._playback_speed_spin)

    def _refresh_specific_fields(self) -> None:
        clip = self._clip
        if not isinstance(clip, VideoClip):
            return

        with block_signals(self._playback_speed_spin):
            self._playback_speed_spin.setValue(clip.playback_speed)

    def _commit_specific_fields(self) -> None:
        clip = self._clip
        if not isinstance(clip, VideoClip):
            return

        self._apply_property_update(clip, "playback_speed", float(self._playback_speed_spin.value()))
