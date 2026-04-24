from __future__ import annotations

from PySide6.QtWidgets import QDoubleSpinBox

from app.domain.clips.audio_clip import AudioClip
from app.ui.inspector._clip_inspector_base import ClipInspectorBase, block_signals


class AudioInspector(ClipInspectorBase):
    def __init__(self, timeline_controller: object, clip: AudioClip, parent=None) -> None:
        super().__init__(timeline_controller, clip, parent)

    def _build_specific_fields(self) -> None:
        self._gain_db_spin = QDoubleSpinBox(self)
        self._gain_db_spin.setRange(-60.0, 12.0)
        self._gain_db_spin.setDecimals(1)
        self._gain_db_spin.setSingleStep(0.5)
        self._gain_db_spin.setKeyboardTracking(False)
        self._gain_db_spin.editingFinished.connect(self._commit_specific_fields)
        self._form.addRow("Gain (dB)", self._gain_db_spin)

    def _refresh_specific_fields(self) -> None:
        clip = self._clip
        if not isinstance(clip, AudioClip):
            return

        with block_signals(self._gain_db_spin):
            self._gain_db_spin.setValue(clip.gain_db)

    def _commit_specific_fields(self) -> None:
        clip = self._clip
        if not isinstance(clip, AudioClip):
            return

        self._apply_property_update(clip, "gain_db", float(self._gain_db_spin.value()))