from __future__ import annotations

from app.controllers.playback_controller import PlaybackController
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


class PlaybackToolbar(QWidget):
    def __init__(self, playback_controller: PlaybackController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._playback_controller = playback_controller

        layout = QHBoxLayout(self)

        self._play_button = QPushButton("Play", self)
        self._pause_button = QPushButton("Pause", self)
        self._stop_button = QPushButton("Stop", self)
        self._time_label = QLabel("00:00.00", self)
        self._time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._time_label.setMinimumWidth(80)

        self._play_button.clicked.connect(self._playback_controller.play)
        self._pause_button.clicked.connect(self._playback_controller.pause)
        self._stop_button.clicked.connect(self._playback_controller.stop)

        self._playback_controller.current_time_changed.connect(self._on_current_time_changed)

        layout.addWidget(self._play_button)
        layout.addWidget(self._pause_button)
        layout.addWidget(self._stop_button)
        layout.addStretch()
        layout.addWidget(self._time_label)

    def _on_current_time_changed(self, current_time: float) -> None:
        total_centiseconds = max(0, int(current_time * 100))
        seconds = (total_centiseconds // 100) % 60
        minutes = total_centiseconds // 6000
        centiseconds = total_centiseconds % 100
        self._time_label.setText(f"{minutes:02d}:{seconds:02d}.{centiseconds:02d}")
