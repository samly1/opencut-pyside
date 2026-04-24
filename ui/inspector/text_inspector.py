from __future__ import annotations

from app.domain.clips.text_clip import TextClip
from app.ui.inspector._clip_inspector_base import ClipInspectorBase, block_signals
from PySide6.QtWidgets import QDoubleSpinBox, QLineEdit


class TextInspector(ClipInspectorBase):
    def __init__(self, timeline_controller: object, clip: TextClip, parent=None) -> None:
        super().__init__(timeline_controller, clip, parent)

    def _build_specific_fields(self) -> None:
        self._content_edit = QLineEdit(self)
        self._content_edit.editingFinished.connect(self._commit_specific_fields)
        self._form.addRow("Content", self._content_edit)

        self._font_size_spin = QDoubleSpinBox(self)
        self._font_size_spin.setRange(8, 512)
        self._font_size_spin.setDecimals(0)
        self._font_size_spin.setSingleStep(4)
        self._font_size_spin.setKeyboardTracking(False)
        self._font_size_spin.editingFinished.connect(self._commit_specific_fields)
        self._form.addRow("Font Size", self._font_size_spin)

        self._color_edit = QLineEdit(self)
        self._color_edit.editingFinished.connect(self._commit_specific_fields)
        self._form.addRow("Color", self._color_edit)

        self._pos_x_spin = QDoubleSpinBox(self)
        self._pos_x_spin.setRange(0.0, 1.0)
        self._pos_x_spin.setDecimals(2)
        self._pos_x_spin.setSingleStep(0.05)
        self._pos_x_spin.setKeyboardTracking(False)
        self._pos_x_spin.editingFinished.connect(self._commit_specific_fields)
        self._form.addRow("Pos X", self._pos_x_spin)

        self._pos_y_spin = QDoubleSpinBox(self)
        self._pos_y_spin.setRange(0.0, 1.0)
        self._pos_y_spin.setDecimals(2)
        self._pos_y_spin.setSingleStep(0.05)
        self._pos_y_spin.setKeyboardTracking(False)
        self._pos_y_spin.editingFinished.connect(self._commit_specific_fields)
        self._form.addRow("Pos Y", self._pos_y_spin)

    def _refresh_specific_fields(self) -> None:
        clip = self._clip
        if not isinstance(clip, TextClip):
            return

        with block_signals(
            self._content_edit,
            self._font_size_spin,
            self._color_edit,
            self._pos_x_spin,
            self._pos_y_spin,
        ):
            self._content_edit.setText(clip.content)
            self._font_size_spin.setValue(clip.font_size)
            self._color_edit.setText(clip.color)
            self._pos_x_spin.setValue(clip.position_x)
            self._pos_y_spin.setValue(clip.position_y)

    def _commit_specific_fields(self) -> None:
        clip = self._clip
        if not isinstance(clip, TextClip):
            return

        self._apply_property_update(clip, "content", self._content_edit.text())
        self._apply_property_update(clip, "font_size", int(self._font_size_spin.value()))
        self._apply_property_update(clip, "color", self._color_edit.text())
        self._apply_property_update(clip, "position_x", float(self._pos_x_spin.value()))
        self._apply_property_update(clip, "position_y", float(self._pos_y_spin.value()))
