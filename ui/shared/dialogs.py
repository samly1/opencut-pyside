from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget


def confirm_action(parent: QWidget, title: str, message: str) -> bool:
    response = QMessageBox.question(
        parent,
        title,
        message,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    return response == QMessageBox.StandardButton.Yes


def show_error(parent: QWidget, title: str, message: str) -> None:
    QMessageBox.critical(parent, title, message)


def show_warning(parent: QWidget, title: str, message: str) -> None:
    QMessageBox.warning(parent, title, message)


def show_info(parent: QWidget, title: str, message: str) -> None:
    QMessageBox.information(parent, title, message)


def select_open_file(
    parent: QWidget,
    title: str = "Open File",
    directory: str = "",
    file_filter: str = "All Files (*.*)",
) -> str | None:
    selected_path, _ = QFileDialog.getOpenFileName(parent, title, directory, file_filter)
    return selected_path or None


def select_open_files(
    parent: QWidget,
    title: str = "Open Files",
    directory: str = "",
    file_filter: str = "All Files (*.*)",
) -> list[str]:
    selected_paths, _ = QFileDialog.getOpenFileNames(parent, title, directory, file_filter)
    return selected_paths


def select_save_file(
    parent: QWidget,
    title: str = "Save File",
    directory: str = "",
    file_filter: str = "All Files (*.*)",
    default_suffix: str = "",
) -> str | None:
    selected_path, _ = QFileDialog.getSaveFileName(parent, title, directory, file_filter)
    if not selected_path:
        return None

    if default_suffix:
        normalized = Path(selected_path)
        if normalized.suffix.lower() != f".{default_suffix.lower().lstrip('.')}":
            normalized = normalized.with_suffix(f".{default_suffix.lstrip('.')}")
        return str(normalized)

    return selected_path


def select_directory(
    parent: QWidget,
    title: str = "Select Directory",
    directory: str = "",
) -> str | None:
    selected_path = QFileDialog.getExistingDirectory(parent, title, directory)
    return selected_path or None
