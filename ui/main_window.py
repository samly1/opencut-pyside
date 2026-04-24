from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow, QMessageBox, QToolBar

from app.controllers.app_controller import AppController
from app.ui.app_shell import AppShell


class MainWindow(QMainWindow):
    def __init__(self, app_controller: AppController) -> None:
        super().__init__()
        self._app_controller = app_controller
        self._export_action: QAction | None = None
        self.setWindowTitle("OpenCut PySide")
        self.resize(1280, 768)
        self._app_shell = AppShell(app_controller=self._app_controller)
        self.setCentralWidget(self._app_shell)
        self._build_project_toolbar()
        self._build_timeline_toolbar()
        self._app_controller.project_controller.project_changed.connect(self._refresh_window_title)
        self._app_controller.dirty_state_changed.connect(self._refresh_window_title)
        self._app_controller.timeline_controller.timeline_edited.connect(self._refresh_window_title)
        self._app_controller.export_controller.export_started.connect(self._on_export_started)
        self._app_controller.export_controller.export_progress_changed.connect(self._on_export_progress_changed)
        self._app_controller.export_controller.export_finished.connect(self._on_export_finished)
        self._app_controller.export_controller.export_failed.connect(self._on_export_failed)
        self._app_controller.export_controller.export_in_progress_changed.connect(self._on_export_in_progress_changed)
        self._app_controller.autosave_failed.connect(self._on_autosave_failed)
        self._refresh_window_title()
        QTimer.singleShot(0, self._offer_autosave_recovery_on_startup)

    def _build_project_toolbar(self) -> None:
        toolbar = QToolBar("Project", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        load_action = QAction("Load", self)
        load_action.setShortcut(QKeySequence.StandardKey.Open)
        load_action.triggered.connect(self._on_load_project_triggered)

        save_action = QAction("Save", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self._on_save_project_triggered)

        save_as_action = QAction("Save As", self)
        save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        save_as_action.triggered.connect(self._on_save_project_as_triggered)

        self._export_action = QAction("Export MP4", self)
        self._export_action.setShortcut(QKeySequence("Ctrl+Shift+E"))
        self._export_action.triggered.connect(self._on_export_project_triggered)

        toolbar.addAction(load_action)
        toolbar.addAction(save_action)
        toolbar.addAction(save_as_action)
        toolbar.addAction(self._export_action)

    def _build_timeline_toolbar(self) -> None:
        toolbar = QToolBar("Timeline", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        undo_action = QAction("Undo", self)
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        undo_action.triggered.connect(self._on_undo_triggered)

        redo_action = QAction("Redo", self)
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        redo_action.triggered.connect(self._on_redo_triggered)

        play_action = QAction("Play/Pause", self)
        play_action.setShortcut(QKeySequence("Space"))
        play_action.triggered.connect(self._on_play_pause_toggled)

        stop_action = QAction("Stop", self)
        stop_action.setShortcut(QKeySequence("Shift+Space"))
        stop_action.triggered.connect(self._on_stop_triggered)

        toolbar.addAction(undo_action)
        toolbar.addAction(redo_action)
        toolbar.addSeparator()
        toolbar.addAction(play_action)
        toolbar.addAction(stop_action)
        toolbar.addSeparator()

        zoom_in_action = QAction("Zoom In", self)
        zoom_in_action.setShortcut(QKeySequence("Ctrl+="))
        zoom_in_action.triggered.connect(self._app_shell.timeline_view.zoom_in)

        zoom_out_action = QAction("Zoom Out", self)
        zoom_out_action.setShortcut(QKeySequence("Ctrl+-"))
        zoom_out_action.triggered.connect(self._app_shell.timeline_view.zoom_out)

        toolbar.addAction(zoom_in_action)
        toolbar.addAction(zoom_out_action)

    def _on_undo_triggered(self) -> None:
        self._app_controller.timeline_controller.undo()

    def _on_redo_triggered(self) -> None:
        self._app_controller.timeline_controller.redo()

    def _on_play_pause_toggled(self) -> None:
        self._app_controller.playback_controller.toggle_play_pause()

    def _on_stop_triggered(self) -> None:
        self._app_controller.playback_controller.stop()

    def _on_load_project_triggered(self) -> None:
        selected_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Project",
            "",
            "Project Files (*.json);;All Files (*.*)",
        )
        if not selected_path:
            return

        if not self._confirm_discard_unsaved_changes("load another project"):
            return

        try:
            self._app_controller.load_project_from_file(selected_path)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Load Project Failed", str(exc))
            return

        self._app_controller.playback_controller.stop()
        self.statusBar().showMessage(f"Loaded project: {selected_path}", 3000)

    def _on_save_project_triggered(self) -> None:
        saved_path = self._save_current_project()
        if saved_path is None:
            return

        self.statusBar().showMessage(f"Saved project: {saved_path}", 3000)

    def _on_save_project_as_triggered(self) -> None:
        saved_path = self._save_current_project(force_prompt=True)
        if saved_path is None:
            return

        self.statusBar().showMessage(f"Saved project: {saved_path}", 3000)

    def _on_export_project_triggered(self) -> None:
        project = self._app_controller.project_controller.active_project()
        if project is None:
            QMessageBox.warning(self, "Export Project", "No active project to export.")
            return

        project_path = self._app_controller.project_controller.active_project_path()
        default_directory = Path(project_path).parent if project_path else Path.cwd()
        default_name = self._safe_filename(project.name or "export")
        default_path = default_directory / f"{default_name}.mp4"

        selected_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export MP4",
            str(default_path),
            "MP4 Video (*.mp4);;All Files (*.*)",
        )
        if not selected_path:
            return

        normalized_path = Path(selected_path)
        if normalized_path.suffix.lower() != ".mp4":
            normalized_path = normalized_path.with_suffix(".mp4")

        try:
            self._app_controller.export_controller.export_active_project(str(normalized_path))
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.critical(self, "Export Failed", str(exc))
            return

    def _prompt_save_path(self) -> str | None:
        selected_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project",
            "",
            "Project Files (*.json);;All Files (*.*)",
        )
        if not selected_path:
            return None

        normalized_path = Path(selected_path)
        if normalized_path.suffix.lower() != ".json":
            normalized_path = normalized_path.with_suffix(".json")
        return str(normalized_path)

    @staticmethod
    def _safe_filename(name: str) -> str:
        cleaned_name = "".join(character if character not in '<>:"/\\|?*' else "_" for character in name).strip()
        return cleaned_name or "export"

    def _on_export_started(self, output_path: str) -> None:
        self.statusBar().showMessage(f"Exporting: {output_path}", 0)

    def _on_export_progress_changed(self, percent: float, message: str) -> None:
        progress_message = f"Exporting... {max(0.0, min(percent, 100.0)):.0f}%"
        if message:
            progress_message = f"{progress_message} - {message}"
        self.statusBar().showMessage(progress_message, 0)

    def _on_export_finished(self, export_result: object) -> None:
        output_path = getattr(export_result, "output_path", str(export_result))
        warnings = getattr(export_result, "warnings", [])
        if warnings:
            self.statusBar().showMessage(f"Exported: {output_path} ({len(warnings)} warning(s))", 5000)
            return

        self.statusBar().showMessage(f"Exported: {output_path}", 5000)

    def _on_export_failed(self, message: str) -> None:
        self.statusBar().showMessage(f"Export failed: {message}", 5000)
        QMessageBox.critical(self, "Export Failed", message)

    def _on_export_in_progress_changed(self, is_exporting: bool) -> None:
        if self._export_action is not None:
            self._export_action.setEnabled(not is_exporting)

    def _refresh_window_title(self, *_args: object) -> None:
        project = self._app_controller.project_controller.active_project()
        project_name = "Untitled"
        if project is not None and project.name:
            project_name = project.name

        dirty_suffix = " *" if self._app_controller.has_unsaved_changes() else ""

        project_path = self._app_controller.project_controller.active_project_path()
        if project_path:
            self.setWindowTitle(f"OpenCut PySide - {project_name}{dirty_suffix} ({Path(project_path).name})")
            return

        self.setWindowTitle(f"OpenCut PySide - {project_name}{dirty_suffix}")

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._confirm_discard_unsaved_changes("close the app"):
            event.ignore()
            return

        event.accept()

    def _confirm_discard_unsaved_changes(self, action_description: str) -> bool:
        if not self._app_controller.has_unsaved_changes():
            return True

        response = QMessageBox.question(
            self,
            "Unsaved Changes",
            f"The current project has unsaved changes. Do you want to save before you {action_description}?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )

        if response == QMessageBox.StandardButton.Save:
            return self._save_current_project() is not None
        if response == QMessageBox.StandardButton.Discard:
            return True
        return False

    def _save_current_project(self, force_prompt: bool = False) -> str | None:
        project_controller = self._app_controller.project_controller
        target_path = None if force_prompt else project_controller.active_project_path()
        if target_path is None:
            target_path = self._prompt_save_path()
            if target_path is None:
                return None

        try:
            saved_path = self._app_controller.save_active_project(target_path)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Save Project Failed", str(exc))
            return None

        if saved_path is None:
            QMessageBox.warning(self, "Save Project", "No active project to save.")
            return None

        return saved_path

    def _offer_autosave_recovery_on_startup(self) -> None:
        app = QApplication.instance()
        if app is not None and app.platformName().lower() == "offscreen":
            return

        if not self._app_controller.has_recoverable_autosave():
            return

        response = QMessageBox.question(
            self,
            "Recover Autosave",
            "A recoverable autosave snapshot was found.\n\n"
            "Would you like to recover it?\n\n"
            f"{self._app_controller.autosave_summary()}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if response == QMessageBox.StandardButton.Yes:
            recovered = self._app_controller.recover_from_autosave()
            if recovered:
                self.statusBar().showMessage("Recovered project from autosave.", 4000)
            else:
                QMessageBox.warning(self, "Recover Autosave", "Unable to recover autosave snapshot.")
            return

        self._app_controller.discard_autosave_snapshot()

    def _on_autosave_failed(self, message: str) -> None:
        self.statusBar().showMessage(f"Autosave failed: {message}", 5000)
