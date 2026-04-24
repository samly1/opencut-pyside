from __future__ import annotations

from pathlib import Path

from app.controllers.project_controller import ProjectController
from app.domain.media_asset import MediaAsset
from app.ui.media_panel.media_item_widget import MediaListWidget
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QListWidgetItem, QPushButton, QVBoxLayout, QWidget


class MediaPanel(QWidget):
    def __init__(self, project_controller: ProjectController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project_controller = project_controller

        layout = QVBoxLayout(self)
        self.import_button = QPushButton("Import Media", self)
        self.media_list = MediaListWidget(self)

        self.import_button.clicked.connect(self._on_import_clicked)
        self._project_controller.project_changed.connect(self._refresh_media_items)

        layout.addWidget(self.import_button)
        layout.addWidget(self.media_list)

        self._refresh_media_items()

    def _on_import_clicked(self) -> None:
        selected_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Import Media Files",
            "",
            "Media Files (*.mp4 *.mov *.mkv *.avi *.webm *.m4v *.mp3 *.wav *.aac *.flac *.ogg *.m4a *.png *.jpg *.jpeg *.bmp *.gif *.webp);;All Files (*.*)",
        )
        if not selected_paths:
            return

        self._project_controller.import_media_files(selected_paths)

    def _refresh_media_items(self) -> None:
        self.media_list.clear()

        project = self._project_controller.active_project()
        if project is None or not project.media_items:
            self.media_list.addItem("No media imported")
            return

        for media_asset in project.media_items:
            item = QListWidgetItem(self._format_media_asset(media_asset))
            item.setData(Qt.ItemDataRole.UserRole, media_asset.media_id)
            self.media_list.addItem(item)

    @staticmethod
    def _format_media_asset(media_asset: MediaAsset) -> str:
        file_name = Path(media_asset.file_path).name if media_asset.file_path else media_asset.name
        media_type = media_asset.media_type.upper()
        if media_asset.file_size_bytes is None:
            return f"[{media_type}] {file_name}"

        file_size_mb = media_asset.file_size_bytes / (1024 * 1024)
        return f"[{media_type}] {file_name} ({file_size_mb:.1f} MB)"
