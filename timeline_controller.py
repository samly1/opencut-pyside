from __future__ import annotations

from typing import Literal
from uuid import uuid4

from PySide6.QtCore import QObject, Signal

from app.controllers.project_controller import ProjectController
from app.controllers.selection_controller import SelectionController
from app.domain.clips.audio_clip import AudioClip
from app.domain.clips.base_clip import BaseClip
from app.domain.clips.image_clip import ImageClip
from app.domain.clips.video_clip import VideoClip
from app.domain.commands import AddClipCommand, CommandManager, DeleteClipCommand, MoveClipCommand, SplitClipCommand, TrimClipCommand
from app.domain.commands.base_command import BaseCommand
from app.domain.media_asset import MediaAsset
from app.domain.project import Project
from app.domain.snap_engine import SnapEngine
from app.domain.timeline import Timeline
from app.domain.track import Track


class TimelineController(QObject):
    timeline_changed = Signal()
    timeline_edited = Signal()

    def __init__(
        self,
        project_controller: ProjectController,
        selection_controller: SelectionController,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._project_controller = project_controller
        self._selection_controller = selection_controller
        self._command_manager = CommandManager()

        self._pixels_per_second = 90.0
        self._snap_threshold_pixels = 10.0
        self._playhead_seconds = 3.5
        self._minimum_clip_duration_seconds = 16.0 / self._pixels_per_second

        self._min_pps = 10.0
        self._max_pps = 2000.0
        self._zoom_factor = 1.2

        self._project_controller.project_changed.connect(self._on_project_changed)

    @property
    def pixels_per_second(self) -> float:
        return self._pixels_per_second

    def set_pixels_per_second(self, pps: float) -> None:
        new_pps = max(self._min_pps, min(pps, self._max_pps))
        if abs(new_pps - self._pixels_per_second) < 1e-6:
            return

        self._pixels_per_second = new_pps
        # Keep 16px minimum width for clips visually
        self._minimum_clip_duration_seconds = 16.0 / self._pixels_per_second
        self.timeline_changed.emit()

    def zoom_in(self) -> None:
        self.set_pixels_per_second(self._pixels_per_second * self._zoom_factor)

    def zoom_out(self) -> None:
        self.set_pixels_per_second(self._pixels_per_second / self._zoom_factor)

    def get_snap_position(
        self,
        clip_id: str,
        proposed_start: float,
        proposed_duration: float,
        drag_mode: Literal["move", "trim_left", "trim_right"],
    ) -> tuple[float, float, float | None]:
        """
        Returns (snapped_start, snapped_duration, snap_target_time).
        snap_target_time is None if no snapping occurred.
        """
        timeline = self.active_timeline()
        if timeline is None:
            return proposed_start, proposed_duration, None

        clip = self._find_clip(timeline, clip_id)
        threshold_seconds = self._snap_threshold_seconds()
        targets = self._collect_snap_targets(timeline=timeline, exclude_clip_id=clip.clip_id)

        if drag_mode == "move":
            snap_delta = SnapEngine.best_move_delta(
                start=proposed_start,
                duration=proposed_duration,
                targets=targets,
                threshold=threshold_seconds,
            )
            if snap_delta is not None:
                snapped_start = max(0.0, proposed_start + snap_delta)
                # Find the target time for the guide line
                snapped_end = snapped_start + proposed_duration
                for t in targets:
                    if abs(snapped_start - t) < 1e-6 or abs(snapped_end - t) < 1e-6:
                        return snapped_start, proposed_duration, t
            return proposed_start, proposed_duration, None

        if drag_mode == "trim_left":
            snapped_start = SnapEngine.snap_value(proposed_start, targets, threshold_seconds)
            if snapped_start is not None:
                right_edge = clip.timeline_end
                max_left = right_edge - self._minimum_clip_duration_seconds
                final_left = min(max(snapped_start, 0.0), max_left)
                return final_left, right_edge - final_left, snapped_start
            return proposed_start, proposed_duration, None

        if drag_mode == "trim_right":
            proposed_right = proposed_start + proposed_duration
            snapped_right = SnapEngine.snap_value(proposed_right, targets, threshold_seconds)
            if snapped_right is not None:
                min_right = clip.timeline_start + self._minimum_clip_duration_seconds
                final_right = max(snapped_right, min_right)
                return clip.timeline_start, final_right - clip.timeline_start, snapped_right
            return proposed_start, proposed_duration, None

        return proposed_start, proposed_duration, None

    def configure_timeline_metrics(
        self,
        pixels_per_second: float,
        snap_threshold_pixels: float,
        playhead_seconds: float,
        minimum_clip_duration_seconds: float,
    ) -> None:
        if pixels_per_second <= 0:
            raise ValueError("pixels_per_second must be > 0")
        if snap_threshold_pixels < 0:
            raise ValueError("snap_threshold_pixels must be >= 0")
        if minimum_clip_duration_seconds <= 0:
            raise ValueError("minimum_clip_duration_seconds must be > 0")

        self._pixels_per_second = pixels_per_second
        self._snap_threshold_pixels = snap_threshold_pixels
        self._playhead_seconds = max(0.0, playhead_seconds)
        self._minimum_clip_duration_seconds = minimum_clip_duration_seconds

    def set_playhead_seconds(self, playhead_seconds: float) -> None:
        self._playhead_seconds = max(0.0, playhead_seconds)

    def active_project(self) -> Project | None:
        return self._project_controller.active_project()

    def active_timeline(self) -> Timeline | None:
        active_project = self.active_project()
        if active_project is None:
            return None
        return active_project.timeline

    def add_clip_from_media(
        self,
        media_id: str,
        timeline_start: float,
        preferred_track_id: str | None = None,
    ) -> str | None:
        project = self.active_project()
        timeline = self.active_timeline()
        if project is None or timeline is None:
            return None

        media_asset = self._find_media_asset(project, media_id)
        target_track = self._select_target_track(timeline, media_asset.media_type, preferred_track_id)
        if target_track is None:
            return None

        clip = self._build_clip_from_media(media_asset, target_track.track_id, max(0.0, timeline_start))
        self._command_manager.execute(
            AddClipCommand(
                timeline=timeline,
                track_id=target_track.track_id,
                clip=clip,
            )
        )
        self.timeline_changed.emit()
        self.timeline_edited.emit()
        return clip.clip_id

    def move_clip(self, clip_id: str, new_timeline_start: float) -> bool:
        timeline = self.active_timeline()
        if timeline is None:
            return False

        clip = self._find_clip(timeline, clip_id)
        snapped_start = self._apply_move_snapping(
            timeline=timeline,
            clip=clip,
            proposed_start=max(0.0, new_timeline_start),
        )

        self._command_manager.execute(
            MoveClipCommand(
                timeline=timeline,
                clip_id=clip_id,
                new_timeline_start=snapped_start,
            )
        )
        self.timeline_changed.emit()
        self.timeline_edited.emit()
        return True

    def trim_clip(
        self,
        clip_id: str,
        new_timeline_start: float,
        new_duration: float,
        trim_side: Literal["left", "right"] | None = None,
    ) -> bool:
        timeline = self.active_timeline()
        if timeline is None:
            return False

        clip = self._find_clip(timeline, clip_id)
        snapped_start, snapped_duration = self._apply_trim_snapping(
            timeline=timeline,
            clip=clip,
            proposed_start=max(0.0, new_timeline_start),
            proposed_duration=max(new_duration, self._minimum_clip_duration_seconds),
            trim_side=trim_side,
        )

        self._command_manager.execute(
            TrimClipCommand(
                timeline=timeline,
                clip_id=clip_id,
                new_timeline_start=snapped_start,
                new_duration=snapped_duration,
            )
        )
        self.timeline_changed.emit()
        self.timeline_edited.emit()
        return True

    def split_clip(self, clip_id: str, split_timeline_position: float) -> tuple[str, str] | None:
        timeline = self.active_timeline()
        if timeline is None:
            return None

        command = SplitClipCommand(
            timeline=timeline,
            clip_id=clip_id,
            split_timeline_position=split_timeline_position,
        )
        self._command_manager.execute(command)
        self.timeline_changed.emit()
        self.timeline_edited.emit()
        return (command.left_clip_id, command.right_clip_id)

    def split_selected_clip(self, split_timeline_position: float) -> bool:
        selected_clip_id = self._selection_controller.selected_clip_id()
        if selected_clip_id is None:
            return False

        try:
            split_result = self.split_clip(selected_clip_id, split_timeline_position)
        except ValueError:
            return False

        if split_result is None:
            return False

        _, right_clip_id = split_result
        self._selection_controller.select_clip(right_clip_id)
        return True

    def delete_selected_clip(self) -> bool:
        timeline = self.active_timeline()
        if timeline is None:
            return False

        selected_clip_id = self._selection_controller.selected_clip_id()
        if selected_clip_id is None:
            return False

        try:
            self._command_manager.execute(DeleteClipCommand(timeline=timeline, clip_id=selected_clip_id))
        except ValueError:
            self._selection_controller.clear_selection()
            return False

        self._selection_controller.clear_selection()
        self.timeline_changed.emit()
        self.timeline_edited.emit()
        return True

    def undo(self) -> bool:
        did_undo = self._command_manager.undo()
        if did_undo:
            self.timeline_changed.emit()
            self.timeline_edited.emit()
        return did_undo

    def redo(self) -> bool:
        did_redo = self._command_manager.redo()
        if did_redo:
            self.timeline_changed.emit()
            self.timeline_edited.emit()
        return did_redo

    def execute_command(self, command: BaseCommand) -> None:
        self._command_manager.execute(command)
        self.timeline_changed.emit()
        self.timeline_edited.emit()

    def _on_project_changed(self) -> None:
        self._command_manager = CommandManager()
        self.timeline_changed.emit()

    def _apply_move_snapping(self, timeline: Timeline, clip: BaseClip, proposed_start: float) -> float:
        threshold_seconds = self._snap_threshold_seconds()
        if threshold_seconds <= 0:
            return proposed_start

        targets = self._collect_snap_targets(timeline=timeline, exclude_clip_id=clip.clip_id)
        snap_delta = SnapEngine.best_move_delta(
            start=proposed_start,
            duration=clip.duration,
            targets=targets,
            threshold=threshold_seconds,
        )
        if snap_delta is None:
            return proposed_start

        return max(0.0, proposed_start + snap_delta)

    def _apply_trim_snapping(
        self,
        timeline: Timeline,
        clip: BaseClip,
        proposed_start: float,
        proposed_duration: float,
        trim_side: Literal["left", "right"] | None,
    ) -> tuple[float, float]:
        side = self._resolve_trim_side(clip, proposed_start, proposed_duration, trim_side)
        threshold_seconds = self._snap_threshold_seconds()
        targets = self._collect_snap_targets(timeline=timeline, exclude_clip_id=clip.clip_id)

        if side == "left":
            right_edge = clip.timeline_end
            left_edge = proposed_start
            snapped_left = SnapEngine.snap_value(left_edge, targets, threshold_seconds)
            final_left = left_edge if snapped_left is None else snapped_left
            max_left = right_edge - self._minimum_clip_duration_seconds
            final_left = min(max(final_left, 0.0), max_left)
            return final_left, right_edge - final_left

        right_edge = clip.timeline_start + proposed_duration
        snapped_right = SnapEngine.snap_value(right_edge, targets, threshold_seconds)
        final_right = right_edge if snapped_right is None else snapped_right
        min_right = clip.timeline_start + self._minimum_clip_duration_seconds
        final_right = max(final_right, min_right)
        return clip.timeline_start, final_right - clip.timeline_start

    def _resolve_trim_side(
        self,
        clip: BaseClip,
        proposed_start: float,
        proposed_duration: float,
        explicit_side: Literal["left", "right"] | None,
    ) -> Literal["left", "right"]:
        if explicit_side in ("left", "right"):
            return explicit_side

        proposed_right = proposed_start + proposed_duration
        moved_left_distance = abs(proposed_start - clip.timeline_start)
        moved_right_distance = abs(proposed_right - clip.timeline_end)
        if moved_left_distance > moved_right_distance:
            return "left"
        return "right"

    def _snap_threshold_seconds(self) -> float:
        if self._pixels_per_second <= 0:
            return 0.0
        return self._snap_threshold_pixels / self._pixels_per_second

    def _collect_snap_targets(self, timeline: Timeline, exclude_clip_id: str) -> list[float]:
        targets = [max(0.0, self._playhead_seconds)]
        for track in timeline.tracks:
            for clip in track.clips:
                if clip.clip_id == exclude_clip_id:
                    continue
                targets.append(clip.timeline_start)
                targets.append(clip.timeline_end)
        return targets

    def _find_clip(self, timeline: Timeline, clip_id: str) -> BaseClip:
        for track in timeline.tracks:
            for clip in track.clips:
                if clip.clip_id == clip_id:
                    return clip
        raise ValueError(f"Clip '{clip_id}' not found in timeline")

    @staticmethod
    def _find_media_asset(project: Project, media_id: str) -> MediaAsset:
        for media_asset in project.media_items:
            if media_asset.media_id == media_id:
                return media_asset
        raise ValueError(f"Media asset '{media_id}' not found in project")

    def _select_target_track(
        self,
        timeline: Timeline,
        media_type: str,
        preferred_track_id: str | None,
    ) -> Track | None:
        preferred_track: Track | None = None
        for track in timeline.tracks:
            if track.track_id == preferred_track_id:
                preferred_track = track
                break

        if preferred_track is not None and self._is_track_compatible(media_type, preferred_track.track_type):
            return preferred_track

        for track in timeline.tracks:
            if self._is_track_compatible(media_type, track.track_type):
                return track

        if preferred_track is not None:
            return preferred_track

        if timeline.tracks:
            return timeline.tracks[0]
        return None

    @staticmethod
    def _is_track_compatible(media_type: str, track_type: str) -> bool:
        normalized_media_type = media_type.lower()
        normalized_track_type = track_type.lower()

        if normalized_track_type == "mixed":
            return True
        if normalized_media_type == "audio":
            return normalized_track_type == "audio"
        if normalized_media_type == "video":
            return normalized_track_type == "video"
        if normalized_media_type == "image":
            return normalized_track_type in {"video", "overlay", "text", "mixed"}
        return True

    def _build_clip_from_media(self, media_asset: MediaAsset, track_id: str, timeline_start: float) -> BaseClip:
        media_type = media_asset.media_type.lower()
        clip_id = f"clip_{uuid4().hex[:10]}"
        duration = self._default_duration_for_media(media_asset)
        source_end = media_asset.duration_seconds if media_asset.duration_seconds and media_asset.duration_seconds > 0 else None

        if media_type == "audio":
            return AudioClip(
                clip_id=clip_id,
                name=media_asset.name,
                track_id=track_id,
                media_id=media_asset.media_id,
                timeline_start=timeline_start,
                duration=duration,
                source_start=0.0,
                source_end=source_end,
            )

        if media_type == "image":
            return ImageClip(
                clip_id=clip_id,
                name=media_asset.name,
                track_id=track_id,
                media_id=media_asset.media_id,
                timeline_start=timeline_start,
                duration=duration,
                source_start=0.0,
                source_end=source_end,
            )

        return VideoClip(
            clip_id=clip_id,
            name=media_asset.name,
            track_id=track_id,
            media_id=media_asset.media_id,
            timeline_start=timeline_start,
            duration=duration,
            source_start=0.0,
            source_end=source_end,
        )

    @staticmethod
    def _default_duration_for_media(media_asset: MediaAsset) -> float:
        if media_asset.duration_seconds is not None and media_asset.duration_seconds > 0:
            return media_asset.duration_seconds
        if media_asset.media_type.lower() == "image":
            return 4.0
        return 5.0
