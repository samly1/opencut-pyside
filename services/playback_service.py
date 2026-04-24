from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.domain.clips.base_clip import BaseClip
from app.domain.clips.image_clip import ImageClip
from app.domain.clips.video_clip import VideoClip
from app.domain.media_asset import MediaAsset
from app.domain.project import Project
from app.infrastructure.ffmpeg_gateway import FFmpegGateway


@dataclass(slots=True, frozen=True)
class PreviewFrameResult:
    frame_bytes: bytes | None
    message: str


class PlaybackService:
    def __init__(self, ffmpeg_gateway: FFmpegGateway | None = None) -> None:
        self._ffmpeg_gateway = ffmpeg_gateway or FFmpegGateway()
        self._last_video_cache_key: tuple[str, float] | None = None
        self._last_video_frame_bytes: bytes | None = None
        self._image_bytes_cache: dict[str, bytes] = {}

    def get_preview_frame(
        self,
        project: Project | None,
        time_seconds: float,
        project_path: str | None = None,
    ) -> PreviewFrameResult:
        if project is None:
            return PreviewFrameResult(frame_bytes=None, message="No project loaded")

        active_clip = self._find_active_visual_clip(project, time_seconds)
        if active_clip is None:
            return PreviewFrameResult(frame_bytes=None, message="No visual clip at current time")

        media_asset = self._find_media_asset(project, active_clip.media_id)
        if media_asset is None:
            return PreviewFrameResult(frame_bytes=None, message="Missing media asset")

        project_root = self._project_root(project_path)
        media_path = self._resolve_media_path(media_asset.file_path, project_root)

        if isinstance(active_clip, ImageClip) or media_asset.media_type.lower() == "image":
            image_bytes = self._load_image_bytes(media_path)
            if image_bytes is None:
                return PreviewFrameResult(frame_bytes=None, message="Unable to load image")
            return PreviewFrameResult(frame_bytes=image_bytes, message=media_asset.name)

        source_time = self._clip_source_time(active_clip, time_seconds)
        source_time = self._clamp_source_time_to_media(source_time, media_asset)
        quantized_source_time = self._quantize_time(source_time, project.fps)
        cache_key = (str(media_path), quantized_source_time)
        if self._last_video_cache_key == cache_key and self._last_video_frame_bytes is not None:
            return PreviewFrameResult(frame_bytes=self._last_video_frame_bytes, message=media_asset.name)

        frame_bytes = self._ffmpeg_gateway.extract_frame_png(str(media_path), quantized_source_time)
        if frame_bytes is None:
            return PreviewFrameResult(frame_bytes=None, message="Unable to decode video frame")

        self._last_video_cache_key = cache_key
        self._last_video_frame_bytes = frame_bytes
        return PreviewFrameResult(frame_bytes=frame_bytes, message=media_asset.name)

    def _find_active_visual_clip(self, project: Project, time_seconds: float) -> BaseClip | None:
        epsilon = 1e-6
        for track in reversed(project.timeline.tracks):
            for clip in reversed(track.sorted_clips()):
                if not isinstance(clip, (VideoClip, ImageClip)):
                    continue
                if clip.timeline_start - epsilon <= time_seconds < clip.timeline_end + epsilon:
                    return clip
        return None

    @staticmethod
    def _find_media_asset(project: Project, media_id: str | None) -> MediaAsset | None:
        if media_id is None:
            return None
        for media_asset in project.media_items:
            if media_asset.media_id == media_id:
                return media_asset
        return None

    @staticmethod
    def _clip_source_time(clip: BaseClip, time_seconds: float) -> float:
        local_offset = max(0.0, time_seconds - clip.timeline_start)
        source_time = clip.source_start + local_offset
        if clip.source_end is None:
            return source_time
        return max(clip.source_start, min(source_time, clip.source_end))

    @staticmethod
    def _clamp_source_time_to_media(source_time: float, media_asset: MediaAsset) -> float:
        if media_asset.duration_seconds is None:
            return max(0.0, source_time)

        media_duration = max(0.0, media_asset.duration_seconds)
        if media_duration <= 0.0:
            return 0.0

        safe_end = max(0.0, media_duration - 0.001)
        return max(0.0, min(source_time, safe_end))

    @staticmethod
    def _quantize_time(time_seconds: float, fps: float) -> float:
        safe_fps = fps if fps > 0 else 30.0
        frame_index = int(time_seconds * safe_fps)
        return frame_index / safe_fps

    @staticmethod
    def _project_root(project_path: str | None) -> Path | None:
        if project_path is None or not project_path.strip():
            return None

        resolved_path = Path(project_path).expanduser().resolve()
        if resolved_path.is_dir():
            return resolved_path
        return resolved_path.parent

    @staticmethod
    def _resolve_media_path(file_path: str, project_root: Path | None) -> Path:
        raw_path = Path(file_path).expanduser()
        if raw_path.is_absolute():
            return raw_path.resolve()

        if project_root is not None:
            return (project_root / raw_path).resolve()

        return raw_path.resolve()

    def _load_image_bytes(self, file_path: Path) -> bytes | None:
        normalized_path = str(file_path.expanduser().resolve())
        cached = self._image_bytes_cache.get(normalized_path)
        if cached is not None:
            return cached

        try:
            image_bytes = Path(normalized_path).read_bytes()
        except OSError:
            return None

        if not image_bytes:
            return None

        self._image_bytes_cache[normalized_path] = image_bytes
        return image_bytes