from __future__ import annotations

from app.domain.selection import SelectionState
from PySide6.QtCore import QObject, Signal


class SelectionController(QObject):
    selection_changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._state = SelectionState()

    def selected_clip_id(self) -> str | None:
        return self._state.selected_clip_id

    def select_clip(self, clip_id: str) -> None:
        if clip_id == self._state.selected_clip_id:
            return
        self._state.selected_clip_id = clip_id
        self.selection_changed.emit()

    def clear_selection(self) -> None:
        if self._state.selected_clip_id is None:
            return
        self._state.selected_clip_id = None
        self.selection_changed.emit()
