from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QStyle, QApplication


_ICON_DIR = Path(__file__).resolve().parents[2] / "resources" / "icons"


class IconProvider:
    @staticmethod
    @lru_cache(maxsize=128)
    def icon(name: str) -> QIcon:
        icon_path = _ICON_DIR / f"{name}.png"
        if icon_path.exists():
            return QIcon(str(icon_path))

        svg_path = _ICON_DIR / f"{name}.svg"
        if svg_path.exists():
            return QIcon(str(svg_path))

        return QIcon()

    @staticmethod
    def standard_icon(standard_pixmap: QStyle.StandardPixmap) -> QIcon:
        app = QApplication.instance()
        if app is None:
            return QIcon()
        style = app.style()
        if style is None:
            return QIcon()
        return style.standardIcon(standard_pixmap)

    @staticmethod
    @lru_cache(maxsize=128)
    def pixmap(name: str, width: int = 24, height: int = 24) -> QPixmap:
        loaded_icon = IconProvider.icon(name)
        if loaded_icon.isNull():
            return QPixmap()
        return loaded_icon.pixmap(width, height)

    @staticmethod
    def play_icon() -> QIcon:
        return IconProvider.standard_icon(QStyle.StandardPixmap.SP_MediaPlay)

    @staticmethod
    def pause_icon() -> QIcon:
        return IconProvider.standard_icon(QStyle.StandardPixmap.SP_MediaPause)

    @staticmethod
    def stop_icon() -> QIcon:
        return IconProvider.standard_icon(QStyle.StandardPixmap.SP_MediaStop)

    @staticmethod
    def open_icon() -> QIcon:
        return IconProvider.standard_icon(QStyle.StandardPixmap.SP_DialogOpenButton)

    @staticmethod
    def save_icon() -> QIcon:
        return IconProvider.standard_icon(QStyle.StandardPixmap.SP_DialogSaveButton)
