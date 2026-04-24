from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from app.domain.clips.base_clip import BaseClip
from app.domain.commands.update_property import UpdatePropertyCommand


class InspectorController(QObject):
    inspector_changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

    def update_clip_property(self, clip: BaseClip, attribute_name: str, new_value: object) -> None:
        from app.controllers.app_controller import AppController

        app_controller = self.parent()
        if not isinstance(app_controller, AppController):
            return

        command = UpdatePropertyCommand(
            target=clip,
            attribute_name=attribute_name,
            new_value=new_value,
        )
        app_controller.timeline_controller.execute_command(command)
        self.inspector_changed.emit()
