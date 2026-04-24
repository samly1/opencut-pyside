from __future__ import annotations

from app.controllers.playback_controller import PlaybackController
from app.controllers.selection_controller import SelectionController
from app.controllers.timeline_controller import TimelineController
from app.services.thumbnail_service import ThumbnailService
from app.ui.media_panel.media_item_widget import media_id_from_mime_data
from app.ui.timeline.clip_item import ClipItem
from app.ui.timeline.timeline_scene import TimelineScene
from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QCursor,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QResizeEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import QFrame, QGraphicsItem, QGraphicsView, QWidget


class TimelineView(QGraphicsView):
    def __init__(
        self,
        timeline_controller: TimelineController,
        playback_controller: PlaybackController,
        selection_controller: SelectionController,
        thumbnail_service: ThumbnailService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._timeline_controller = timeline_controller
        self._playback_controller = playback_controller
        self._selection_controller = selection_controller
        self._timeline_scene = TimelineScene(
            project=self._timeline_controller.active_project(),
            project_path=self._timeline_controller.active_project_path(),
            thumbnail_service=thumbnail_service,
            parent=self,
        )
        self.setScene(self._timeline_scene)
        self.setMinimumHeight(220)

        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)

        self._timeline_controller.timeline_changed.connect(self._refresh_from_controller)
        self._playback_controller.current_time_changed.connect(self._on_playback_time_changed)
        self._selection_controller.selection_changed.connect(self._refresh_selection_from_controller)

        self._timeline_scene.set_selected_clip_id(self._selection_controller.selected_clip_id())
        self._timeline_scene.set_playhead_seconds(self._playback_controller.current_time())

        self._trim_handle_pixels = 8.0
        self._min_clip_pixels = 16.0
        self._snap_threshold_pixels = 10.0

        self._timeline_controller.configure_timeline_metrics(
            pixels_per_second=self._timeline_scene.pixels_per_second,
            snap_threshold_pixels=self._snap_threshold_pixels,
            playhead_seconds=self._playback_controller.current_time(),
            minimum_clip_duration_seconds=self._min_clip_pixels / self._timeline_scene.pixels_per_second,
        )
        self._timeline_controller.set_playhead_seconds(self._playback_controller.current_time())

        self._drag_mode: str | None = None
        self._drag_clip_id: str | None = None
        self._drag_start_scene_x = 0.0
        self._drag_item_start_x = 0.0
        self._drag_item_start_width = 0.0
        self._drag_clip_start_time = 0.0
        self._drag_clip_start_duration = 0.0
        self._is_dragging = False
        self._is_scrubbing = False

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        media_id = media_id_from_mime_data(event.mimeData())
        if media_id is not None:
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        media_id = media_id_from_mime_data(event.mimeData())
        if media_id is not None:
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        media_id = media_id_from_mime_data(event.mimeData())
        if media_id is None:
            super().dropEvent(event)
            return

        scene_pos = self.mapToScene(event.position().toPoint())
        timeline_start = max(
            0.0,
            (scene_pos.x() - self._timeline_scene.left_gutter) / self._timeline_scene.pixels_per_second,
        )
        rounded_timeline_start = round(timeline_start, 3)
        target_track_id = self._timeline_scene.track_id_at_scene_y(scene_pos.y())

        try:
            created_clip_id = self._timeline_controller.add_clip_from_media(
                media_id=media_id,
                timeline_start=rounded_timeline_start,
                preferred_track_id=target_track_id,
            )
        except ValueError:
            created_clip_id = None

        if created_clip_id is None:
            event.ignore()
            return

        self._selection_controller.select_clip(created_clip_id)
        event.acceptProposedAction()

    def zoom_in(self) -> None:
        self._perform_zoom(self._timeline_controller.zoom_in)

    def zoom_out(self) -> None:
        self._perform_zoom(self._timeline_controller.zoom_out)

    def _perform_zoom(self, zoom_fn, anchor_scene_x: float | None = None) -> None:
        if anchor_scene_x is None:
            # Default to center of viewport
            viewport_rect = self.viewport().rect()
            anchor_scene_x = self.mapToScene(viewport_rect.center()).x()

        # View position of anchor (fixed reference)
        anchor_view_x = self.mapFromScene(anchor_scene_x, 0).x()

        # Time at anchor (invariant during zoom)
        old_pps = self._timeline_controller.pixels_per_second
        anchor_time = (anchor_scene_x - self._timeline_scene.left_gutter) / old_pps

        # Execute zoom (triggers signal -> _refresh_from_controller -> render_timeline)
        zoom_fn()

        # Calculate new scene x for the same anchor time
        new_pps = self._timeline_controller.pixels_per_second
        new_scene_x = anchor_time * new_pps + self._timeline_scene.left_gutter

        # Adjust horizontal scrollbar to keep the anchor time at the same view position
        self._set_horizontal_scroll(new_scene_x - anchor_view_x)

    def _set_horizontal_scroll(self, value: float) -> None:
        bar = self.horizontalScrollBar()
        clamped_value = max(bar.minimum(), min(int(value), bar.maximum()))
        bar.setValue(clamped_value)

    def _refresh_from_controller(self) -> None:
        viewport_width = self.viewport().width()
        viewport_height = self.viewport().height()

        self._timeline_scene.pixels_per_second = self._timeline_controller.pixels_per_second
        self._timeline_scene.set_project(
            self._timeline_controller.active_project(),
            project_path=self._timeline_controller.active_project_path(),
            min_width=viewport_width,
            min_height=viewport_height,
        )
        self._timeline_scene.set_selected_clip_id(self._selection_controller.selected_clip_id())

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._refresh_from_controller()

    def _refresh_selection_from_controller(self) -> None:
        self._timeline_scene.set_selected_clip_id(self._selection_controller.selected_clip_id())

    def _on_playback_time_changed(self, time_seconds: float) -> None:
        self._timeline_controller.set_playhead_seconds(time_seconds)
        self._timeline_scene.set_playhead_seconds(time_seconds)

        if not self._is_dragging:
            self._ensure_playhead_visible(time_seconds)

    def _ensure_playhead_visible(self, time_seconds: float) -> None:
        pps = self._timeline_controller.pixels_per_second
        playhead_x = self._timeline_scene.left_gutter + time_seconds * pps

        viewport_rect = self.viewport().rect()
        visible_scene_rect = self.mapToScene(viewport_rect).boundingRect()

        margin_px = 40.0
        is_playing = self._playback_controller.is_playing()

        if is_playing:
            # When playing, scroll if playhead reaches the right edge
            if playhead_x > visible_scene_rect.right() - margin_px:
                # Center the playhead or put it at 20% from left
                new_scroll_x = playhead_x - (viewport_rect.width() * 0.2)
                self._set_horizontal_scroll(new_scroll_x)
        else:
            # When seeking/stopped, ensure playhead is within view with some margin
            if playhead_x < visible_scene_rect.left() + margin_px or playhead_x > visible_scene_rect.right() - margin_px:
                # Center the playhead
                new_scroll_x = playhead_x - (viewport_rect.width() * 0.5)
                self._set_horizontal_scroll(new_scroll_x)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        self.setFocus(Qt.FocusReason.MouseFocusReason)

        scene_pos = self.mapToScene(event.position().toPoint())
        if self._is_ruler_scene_y(scene_pos.y()):
            self._seek_to_scene_x(scene_pos.x())
            self._is_scrubbing = True
            self.setCursor(Qt.CursorShape.SizeHorCursor)
            event.accept()
            return

        scene_item = self.itemAt(event.position().toPoint())
        clip_item = self._clip_item_from_item(scene_item)
        if clip_item is None:
            event.accept()
            return

        clip_id = clip_item.clip.clip_id
        self._selection_controller.select_clip(clip_id)
        active_item = self._find_clip_item_by_id(clip_id)
        if active_item is None:
            event.accept()
            return

        scene_pos = self.mapToScene(event.position().toPoint())
        edge_handle = active_item.hit_test_edge(scene_pos.x(), self._trim_handle_pixels)

        self._drag_mode = "move"
        if edge_handle == "left":
            self._drag_mode = "trim_left"
        elif edge_handle == "right":
            self._drag_mode = "trim_right"

        self._drag_clip_id = clip_id
        self._drag_start_scene_x = scene_pos.x()
        self._drag_item_start_x = active_item.scenePos().x()
        self._drag_item_start_width = active_item.rect().width()
        self._drag_clip_start_time = active_item.clip.timeline_start
        self._drag_clip_start_duration = active_item.clip.duration
        self._is_dragging = True

        if self._drag_mode == "move":
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        else:
            self.setCursor(Qt.CursorShape.SizeHorCursor)

        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._is_scrubbing:
            scene_pos = self.mapToScene(event.position().toPoint())
            self._seek_to_scene_x(scene_pos.x())
            event.accept()
            return

        if not self._is_dragging or self._drag_clip_id is None:
            self._update_hover_cursor(event)
            super().mouseMoveEvent(event)
            return

        clip_item = self._find_clip_item_by_id(self._drag_clip_id)
        if clip_item is None:
            self._cancel_drag()
            self._refresh_from_controller()
            super().mouseMoveEvent(event)
            return

        pps = self._timeline_scene.pixels_per_second
        left_gutter = self._timeline_scene.left_gutter
        scene_pos = self.mapToScene(event.position().toPoint())
        delta_x = scene_pos.x() - self._drag_start_scene_x

        # Calculate proposed timeline coordinates
        if self._drag_mode == "move":
            proposed_x = self._drag_item_start_x + delta_x
            proposed_start = (proposed_x - left_gutter) / pps
            proposed_duration = self._drag_clip_start_duration
        elif self._drag_mode == "trim_left":
            right_edge = self._drag_item_start_x + self._drag_item_start_width
            proposed_x = self._drag_item_start_x + delta_x
            proposed_start = (proposed_x - left_gutter) / pps
            proposed_duration = (right_edge - proposed_x) / pps
        elif self._drag_mode == "trim_right":
            proposed_start = self._drag_clip_start_time
            proposed_duration = (self._drag_item_start_width + delta_x) / pps

        # Get snapped coordinates from controller
        snapped_start, snapped_duration, snap_target_time = self._timeline_controller.get_snap_position(
            self._drag_clip_id, proposed_start, proposed_duration, self._drag_mode
        )

        # Apply to visual item
        display_x = left_gutter + snapped_start * pps
        display_width = snapped_duration * pps

        if self._drag_mode == "move":
            clip_item.setX(display_x)
        else:
            clip_item.set_display_geometry(display_x, display_width)

        # Show/hide snap guide
        if snap_target_time is not None:
            self._timeline_scene.show_snap_guide(left_gutter + snap_target_time * pps)
        else:
            self._timeline_scene.hide_snap_guide()

        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._is_scrubbing:
            self._is_scrubbing = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return

        if event.button() != Qt.MouseButton.LeftButton or not self._is_dragging or self._drag_clip_id is None:
            super().mouseReleaseEvent(event)
            return

        clip_item = self._find_clip_item_by_id(self._drag_clip_id)
        if clip_item is None:
            self._cancel_drag()
            self._refresh_from_controller()
            super().mouseReleaseEvent(event)
            return

        if self._drag_mode == "move":
            pixels_per_second = self._timeline_scene.pixels_per_second
            left_gutter = self._timeline_scene.left_gutter
            scene_x = max(left_gutter, clip_item.scenePos().x())
            new_timeline_start = max(0.0, (scene_x - left_gutter) / pixels_per_second)
            rounded_timeline_start = round(new_timeline_start, 3)

            moved = abs(rounded_timeline_start - self._drag_clip_start_time) > 1e-6
            if moved:
                try:
                    did_move = self._timeline_controller.move_clip(self._drag_clip_id, rounded_timeline_start)
                except ValueError:
                    did_move = False
                if not did_move:
                    self._refresh_from_controller()
            else:
                self._refresh_from_controller()
        else:
            pixels_per_second = self._timeline_scene.pixels_per_second
            left_gutter = self._timeline_scene.left_gutter
            scene_x = max(left_gutter, clip_item.scenePos().x())
            new_timeline_start = max(0.0, (scene_x - left_gutter) / pixels_per_second)
            new_duration = max(self._min_clip_pixels / pixels_per_second, clip_item.rect().width() / pixels_per_second)
            rounded_timeline_start = round(new_timeline_start, 3)
            rounded_duration = round(new_duration, 3)

            trimmed = (
                abs(rounded_timeline_start - self._drag_clip_start_time) > 1e-6
                or abs(rounded_duration - self._drag_clip_start_duration) > 1e-6
            )
            if trimmed:
                try:
                    did_trim = self._timeline_controller.trim_clip(
                        self._drag_clip_id,
                        rounded_timeline_start,
                        rounded_duration,
                        trim_side="left" if self._drag_mode == "trim_left" else "right",
                    )
                except ValueError:
                    did_trim = False
                if not did_trim:
                    self._refresh_from_controller()
            else:
                self._refresh_from_controller()

        self._cancel_drag()
        event.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Delete:
            if self._timeline_controller.delete_selected_clip():
                event.accept()
                return

        if event.key() == Qt.Key.Key_S and event.modifiers() == Qt.KeyboardModifier.NoModifier:
            cursor_pos = self.mapToScene(self.mapFromGlobal(QCursor.pos()))
            split_position = max(
                0.0,
                (cursor_pos.x() - self._timeline_scene.left_gutter) / self._timeline_scene.pixels_per_second,
            )
            rounded_split_position = round(split_position, 3)
            if self._timeline_controller.split_selected_clip(rounded_split_position):
                event.accept()
                return

        if event.key() == Qt.Key.Key_Space and event.modifiers() == Qt.KeyboardModifier.NoModifier:
            if self._playback_controller.is_playing():
                self._playback_controller.pause()
            else:
                self._playback_controller.play()
            event.accept()
            return

        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            step = self._playhead_nudge_step(event.modifiers())
            if step > 0.0:
                direction = -1.0 if event.key() == Qt.Key.Key_Left else 1.0
                new_time = max(0.0, self._playback_controller.current_time() + direction * step)
                self._playback_controller.seek(new_time)
                event.accept()
                return

        if event.key() == Qt.Key.Key_Home and event.modifiers() == Qt.KeyboardModifier.NoModifier:
            self._playback_controller.seek(0.0)
            event.accept()
            return

        super().keyPressEvent(event)

    def _playhead_nudge_step(self, modifiers: Qt.KeyboardModifier) -> float:
        project = self._timeline_controller.active_project()
        fps = project.fps if project is not None and project.fps > 0 else 30.0
        frame_duration = 1.0 / fps
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            return max(frame_duration, 1.0)
        if modifiers == Qt.KeyboardModifier.NoModifier:
            return frame_duration
        return 0.0

    def _is_ruler_scene_y(self, scene_y: float) -> bool:
        return 0.0 <= scene_y <= self._timeline_scene.ruler_height

    def _seek_to_scene_x(self, scene_x: float) -> None:
        pps = self._timeline_scene.pixels_per_second
        if pps <= 0:
            return
        time_seconds = max(0.0, (scene_x - self._timeline_scene.left_gutter) / pps)
        self._playback_controller.seek(round(time_seconds, 4))

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            scene_pos = self.mapToScene(event.position().toPoint())
            delta = event.angleDelta().y()
            if delta > 0:
                self._perform_zoom(self._timeline_controller.zoom_in, anchor_scene_x=scene_pos.x())
            else:
                self._perform_zoom(self._timeline_controller.zoom_out, anchor_scene_x=scene_pos.x())
            event.accept()
        else:
            super().wheelEvent(event)

    def _clip_item_from_item(self, item: QGraphicsItem | None) -> ClipItem | None:
        current = item
        while current is not None:
            if isinstance(current, ClipItem):
                return current
            current = current.parentItem()
        return None

    def _find_clip_item_by_id(self, clip_id: str) -> ClipItem | None:
        for item in self._timeline_scene.items():
            if isinstance(item, ClipItem) and item.clip.clip_id == clip_id:
                return item
        return None

    def _update_hover_cursor(self, event: QMouseEvent) -> None:
        scene_item = self.itemAt(event.position().toPoint())
        clip_item = self._clip_item_from_item(scene_item)
        if clip_item is None:
            self.setCursor(Qt.CursorShape.ArrowCursor)
            return

        scene_pos = self.mapToScene(event.position().toPoint())
        if clip_item.hit_test_edge(scene_pos.x(), self._trim_handle_pixels) is not None:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
            return

        self.setCursor(Qt.CursorShape.ArrowCursor)

    def _cancel_drag(self) -> None:
        self._is_dragging = False
        self._drag_mode = None
        self._drag_clip_id = None
        self._timeline_scene.hide_snap_guide()
        self.setCursor(Qt.CursorShape.ArrowCursor)
