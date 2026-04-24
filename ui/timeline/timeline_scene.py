from __future__ import annotations

from app.domain.clips.audio_clip import AudioClip
from app.domain.clips.base_clip import BaseClip
from app.domain.clips.image_clip import ImageClip
from app.domain.clips.text_clip import TextClip
from app.domain.clips.video_clip import VideoClip
from app.domain.project import Project
from app.domain.track import Track
from app.services.thumbnail_service import ThumbnailService
from app.ui.timeline.clip_item import ClipItem
from app.ui.timeline.playhead_item import PlayheadItem
from app.ui.timeline.ruler_widget import format_seconds_label
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsScene


class TimelineScene(QGraphicsScene):
    def __init__(
        self,
        project: Project | None,
        project_path: str | None,
        thumbnail_service: ThumbnailService,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.pixels_per_second = 90.0
        self.ruler_height = 24.0
        self.track_height = 58.0
        self.track_gap = 10.0
        self.left_gutter = 120.0
        self.right_padding = 60.0
        self.top_padding = 8.0
        self.bottom_padding = 12.0

        self._playhead_seconds = 0.0
        self._playhead_item: PlayheadItem | None = None
        self._snap_guide_item: QGraphicsLineItem | None = None
        self._project = project
        self._project_path = project_path
        self._thumbnail_service = thumbnail_service
        self._selected_clip_id: str | None = None
        self._last_min_width = 0.0
        self._last_min_height = 0.0
        self._ruler_label_specs: list[tuple[float, str]] = []
        self._track_label_specs: list[tuple[float, str]] = []
        self.setBackgroundBrush(QBrush(QColor("#eef3f7")))
        self.render_timeline()

    def set_project(
        self,
        project: Project | None,
        project_path: str | None,
        min_width: float | None = None,
        min_height: float | None = None,
    ) -> None:
        self._project = project
        self._project_path = project_path
        self.render_timeline(min_width=min_width, min_height=min_height)

    def set_selected_clip_id(self, clip_id: str | None) -> None:
        if clip_id == self._selected_clip_id:
            return
        self._selected_clip_id = clip_id
        self._refresh_clip_selection_state()

    def set_playhead_seconds(self, seconds: float) -> None:
        clamped_seconds = max(0.0, seconds)
        if abs(clamped_seconds - self._playhead_seconds) < 1e-6:
            return

        self._playhead_seconds = clamped_seconds
        self._update_playhead(self.sceneRect().height())

    @property
    def playhead_seconds(self) -> float:
        return self._playhead_seconds

    def render_timeline(
        self,
        min_width: float | None = None,
        min_height: float | None = None,
    ) -> None:
        if min_width is not None:
            self._last_min_width = min_width
        if min_height is not None:
            self._last_min_height = min_height

        self.clear()
        self._playhead_item = None
        self._snap_guide_item = None
        self._ruler_label_specs = []
        self._track_label_specs = []

        tracks = self._project.timeline.tracks if self._project is not None else []
        total_duration = 12.0
        if self._project is not None:
            total_duration = max(total_duration, self._project.timeline.total_duration() + 2.0)
        track_count = len(tracks)

        calculated_width = self.left_gutter + (total_duration * self.pixels_per_second) + self.right_padding
        calculated_height = (
            self.ruler_height
            + self.top_padding
            + track_count * self.track_height
            + max(0, track_count - 1) * self.track_gap
            + self.bottom_padding
        )

        scene_width = max(calculated_width, self._last_min_width)
        scene_height = max(calculated_height, self._last_min_height)
        self.setSceneRect(0, 0, scene_width, scene_height)

        ruler_duration = max(
            total_duration,
            max(0.0, (scene_width - self.left_gutter - self.right_padding) / self.pixels_per_second),
        )
        self._draw_ruler(ruler_duration)
        self._draw_tracks(tracks)
        self._update_playhead(scene_height)

    def _draw_ruler(self, duration_seconds: float) -> None:
        ruler_rect = QRectF(0.0, 0.0, self.sceneRect().width(), self.ruler_height)
        border_pen = QPen(QColor("#8693a0"), 1)
        border_pen.setCosmetic(True)

        ruler_item = self.addRect(
            ruler_rect,
            border_pen,
            QBrush(QColor("#ebeff3")),
        )
        ruler_item.setZValue(-10)
        ruler_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

        label_interval, tick_interval = self._get_ruler_intervals(self.pixels_per_second)

        # Draw ticks and labels
        current_tick = 0.0
        # Add a small epsilon to duration to ensure the last tick is drawn
        while current_tick <= duration_seconds + 1e-6:
            x = self.left_gutter + current_tick * self.pixels_per_second

            is_label_tick = False
            # Check if current_tick is a multiple of label_interval
            if label_interval > 0:
                remainder = current_tick % label_interval
                if remainder < 1e-6 or remainder > label_interval - 1e-6:
                    is_label_tick = True

            tick_height = 12 if is_label_tick else 8
            tick_item = self.addLine(x, self.ruler_height - tick_height, x, self.ruler_height, QPen(QColor("#7a8794"), 1))
            tick_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

            if is_label_tick:
                label_text = format_seconds_label(current_tick)
                self._ruler_label_specs.append((x + 4, label_text))

            current_tick += tick_interval

    def _get_ruler_intervals(self, pps: float) -> tuple[float, float]:
        """Returns (label_interval, tick_interval) in seconds."""
        # target_label_dist = 100 pixels
        possible_intervals = [0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0, 120.0, 300.0, 600.0, 1800.0, 3600.0]

        target_dist = 100.0
        label_interval = 1.0
        for interval in possible_intervals:
            if interval * pps >= target_dist:
                label_interval = interval
                break
        else:
            label_interval = possible_intervals[-1]

        # Tick interval is usually 1/5 or 1/2 of label interval
        if label_interval <= 0.5:
            tick_interval = label_interval / 2
        else:
            tick_interval = label_interval / 5

        return label_interval, tick_interval

    def _draw_tracks(self, tracks: list[Track]) -> None:
        for track_index, track in enumerate(tracks):
            y = self.ruler_height + self.top_padding + track_index * (self.track_height + self.track_gap)
            self._draw_track_background(track.name, y)
            self._draw_track_clips(track.sorted_clips(), y)

    def track_id_at_scene_y(self, scene_y: float) -> str | None:
        if self._project is None:
            return None

        for track_index, track in enumerate(self._project.timeline.tracks):
            lane_top = self.ruler_height + self.top_padding + track_index * (self.track_height + self.track_gap)
            lane_bottom = lane_top + self.track_height
            if lane_top <= scene_y <= lane_bottom:
                return track.track_id
        return None

    def _draw_track_background(self, track_title: str, y_position: float) -> None:
        border_pen = QPen(QColor("#7a8794"), 1)
        border_pen.setCosmetic(True)

        label_rect = QRectF(0.0, y_position, self.left_gutter, self.track_height)
        r1 = self.addRect(label_rect, border_pen, QBrush(QColor("#dbe2e9")))
        r1.setZValue(-10)
        r1.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

        self._track_label_specs.append((y_position, track_title))

        lane_rect = QRectF(
            self.left_gutter,
            y_position,
            self.sceneRect().width() - self.left_gutter,
            self.track_height,
        )
        r2 = self.addRect(
            lane_rect,
            border_pen,
            QBrush(QColor("#eef3f7")),
        )
        r2.setZValue(-10)
        r2.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def _draw_track_clips(self, clips: tuple[BaseClip, ...], track_y: float) -> None:
        clip_y = track_y + 8
        clip_height = self.track_height - 16

        for clip in clips:
            clip_x = self.left_gutter + clip.timeline_start * self.pixels_per_second
            clip_width = max(clip.duration * self.pixels_per_second, 16.0)
            rect = QRectF(clip_x, clip_y, clip_width, clip_height)

            thumbnail_pixmap: QPixmap | None = None
            if self._project is not None and isinstance(clip, (VideoClip, ImageClip)):
                thumbnail_bytes = self._thumbnail_service.get_thumbnail_bytes(
                    project=self._project,
                    clip=clip,
                    project_path=self._project_path,
                )
                if thumbnail_bytes:
                    pixmap = QPixmap()
                    if pixmap.loadFromData(thumbnail_bytes):
                        thumbnail_pixmap = pixmap

            self.addItem(
                ClipItem(
                    clip,
                    rect,
                    self._clip_color(clip),
                    thumbnail=thumbnail_pixmap,
                    is_selected=(clip.clip_id == self._selected_clip_id),
                )
            )

    def _refresh_clip_selection_state(self) -> None:
        for item in self.items():
            if isinstance(item, ClipItem):
                item.set_selected_state(item.clip.clip_id == self._selected_clip_id)

    def _update_playhead(self, scene_height: float) -> None:
        if self._playhead_item is not None:
            self.removeItem(self._playhead_item)
            self._playhead_item = None

        playhead_x = self.left_gutter + self._playhead_seconds * self.pixels_per_second
        playhead_bounds = QRectF(playhead_x, self.ruler_height, 0.0, scene_height - self.ruler_height)
        self._playhead_item = PlayheadItem(playhead_x, playhead_bounds)
        self.addItem(self._playhead_item)

    def _clip_color(self, clip: BaseClip) -> str:
        if isinstance(clip, VideoClip):
            return "#9ec8ff"
        if isinstance(clip, ImageClip):
            return "#f9c8ff"
        if isinstance(clip, TextClip):
            return "#ffd9a3"
        if isinstance(clip, AudioClip):
            return "#9be8c7"
        return "#d8dee6"

    def show_snap_guide(self, scene_x: float) -> None:
        self.hide_snap_guide()

        pen = QPen(QColor("#ff4d4d"), 1, Qt.PenStyle.DashLine)
        scene_height = self.sceneRect().height()
        self._snap_guide_item = self.addLine(
            scene_x, self.ruler_height, scene_x, scene_height, pen
        )
        self._snap_guide_item.setZValue(100) # Ensure it's on top
        self._snap_guide_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def hide_snap_guide(self) -> None:
        if self._snap_guide_item:
            try:
                self.removeItem(self._snap_guide_item)
            except RuntimeError:
                # Item was already deleted by self.clear()
                pass
            self._snap_guide_item = None

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:
        super().drawForeground(painter, rect)

        painter.save()
        painter.setPen(QPen(QColor("#7a8794"), 1))
        for y_position, _track_title in self._track_label_specs:
            top_y = y_position
            bottom_y = y_position + self.track_height
            painter.drawLine(QPointF(0.0, top_y), QPointF(self.left_gutter, top_y))
            painter.drawLine(QPointF(0.0, bottom_y), QPointF(self.left_gutter, bottom_y))
            painter.drawLine(QPointF(self.left_gutter, top_y), QPointF(self.left_gutter, bottom_y))

        painter.setPen(QColor("#2e3a46"))
        for x_position, label_text in self._ruler_label_specs:
            painter.drawText(QRectF(x_position, 0.0, 60.0, self.ruler_height), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, label_text)

        painter.setPen(QColor("#1f2933"))
        for y_position, track_title in self._track_label_specs:
            label_rect = QRectF(10.0, y_position + 8.0, self.left_gutter - 20.0, self.track_height - 16.0)
            painter.drawText(label_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, track_title)
        painter.restore()
