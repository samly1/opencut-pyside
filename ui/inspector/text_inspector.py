from __future__ import annotations

from PySide6.QtWidgets import QLineEdit

from app.domain.clips.text_clip import TextClip
from app.ui.inspector._clip_inspector_base import ClipInspectorBase, block_signals


class TextInspector(ClipInspectorBase):
    def __init__(self, timeline_controller: object, clip: TextClip, parent=None) -> None:
        super().__init__(timeline_controller, clip, parent)

    def _build_specific_fields(self) -> None:
        self._content_edit = QLineEdit(self)
        self._content_edit.editingFinished.connect(self._commit_specific_fields)
        self._form.addRow("Content", self._content_edit)

    def _refresh_specific_fields(self) -> None:
        clip = self._clip
        if not isinstance(clip, TextClip):
            return

        with block_signals(self._content_edit):
            self._content_edit.setText(clip.content)

    def _commit_specific_fields(self) -> None:
        clip = self._clip
        if not isinstance(clip, TextClip):
            return

        self._apply_property_update(clip, "content", self._content_edit.text())
