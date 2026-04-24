from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from app.domain.clips.base_clip import BaseClip
from app.domain.clips.image_clip import ImageClip
from app.domain.clips.text_clip import TextClip
from app.domain.clips.video_clip import VideoClip
from app.domain.media_asset import MediaAsset
from app.domain.project import Project
from app.infrastructure.ffmpeg_gateway import FFmpegGateway
from app.infrastructure.video_decoder import VideoDecoder


@dataclass(slots=True, frozen=True)
class PreviewFrameResult:
    frame_bytes: bytes | None
    message: str


class PlaybackService:
    _PREFETCH_WINDOW_SECONDS = 2.2
    _MIN_PREFETCH_FRAME_COUNT = 24
    _MAX_PREFETCH_FRAME_COUNT = 96

    def __init__(
        self,
        ffmpeg_gateway: FFmpegGateway | None = None,
        video_decoder: VideoDecoder | None = None,
    ) -> None:
        self._ffmpeg_gateway = ffmpeg_gateway or FFmpegGateway()
        self._video_decoder = video_decoder or VideoDecoder(ffmpeg_gateway=self._ffmpeg_gateway, max_cache_entries=420)
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

        if isinstance(active_clip, TextClip):
            return self._render_text_clip(active_clip, project)

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
        safe_fps = self._safe_fps(project.fps)
        frame_index = self._frame_index(source_time, safe_fps)
        normalized_media_path = str(media_path)
        cached_frame = self._video_decoder.get_frame(normalized_media_path, safe_fps, frame_index)
        if cached_frame is not None:
            self._prefetch_window(
                media_path=normalized_media_path,
                fps=safe_fps,
                frame_index=frame_index + 1,
                media_asset=media_asset,
            )
            return PreviewFrameResult(frame_bytes=cached_frame, message=media_asset.name)

        self._prefetch_window(
            media_path=normalized_media_path,
            fps=safe_fps,
            frame_index=frame_index,
            media_asset=media_asset,
        )
        cached_frame = self._video_decoder.get_frame(normalized_media_path, safe_fps, frame_index)
        if cached_frame is not None:
            return PreviewFrameResult(frame_bytes=cached_frame, message=media_asset.name)

        quantized_source_time = self._time_from_frame_index(frame_index, safe_fps)
        frame_bytes = self._ffmpeg_gateway.extract_frame_png(normalized_media_path, quantized_source_time)
        if frame_bytes is None:
            return PreviewFrameResult(frame_bytes=None, message="Unable to decode video frame")

        self._video_decoder.put_frame(normalized_media_path, safe_fps, frame_index, frame_bytes)
        return PreviewFrameResult(frame_bytes=frame_bytes, message=media_asset.name)

    def _find_active_visual_clip(self, project: Project, time_seconds: float) -> BaseClip | None:
        epsilon = 1e-6
        for track in reversed(project.timeline.tracks):
            for clip in reversed(track.sorted_clips()):
                if not isinstance(clip, (VideoClip, ImageClip, TextClip)):
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
    def _safe_fps(fps: float) -> float:
        return fps if fps > 0 else 30.0

    @staticmethod
    def _frame_index(time_seconds: float, fps: float) -> int:
        safe_fps = fps if fps > 0 else 30.0
        return int(max(0.0, time_seconds) * safe_fps)

    @staticmethod
    def _time_from_frame_index(frame_index: int, fps: float) -> float:
        safe_fps = fps if fps > 0 else 30.0
        safe_index = max(0, frame_index)
        return safe_index / safe_fps

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

    def _prefetch_window(self, media_path: str, fps: float, frame_index: int, media_asset: MediaAsset) -> None:
        frame_count = self._prefetch_frame_count_for_fps(fps)
        window_start = max(0, frame_index)
        if self._video_decoder.has_prefetched_until(media_path, fps, window_start):
            return
        self._video_decoder.decode_window(
            media_path=media_path,
            fps=fps,
            start_frame_index=window_start,
            frame_count=frame_count,
            media_duration_seconds=media_asset.duration_seconds,
        )

    @classmethod
    def _prefetch_frame_count_for_fps(cls, fps: float) -> int:
        safe_fps = fps if fps > 0 else 30.0
        dynamic_count = int(round(safe_fps * cls._PREFETCH_WINDOW_SECONDS))
        return max(cls._MIN_PREFETCH_FRAME_COUNT, min(cls._MAX_PREFETCH_FRAME_COUNT, dynamic_count))

    @staticmethod
    def _render_text_clip(clip: TextClip, project: Project) -> PreviewFrameResult:
        from PySide6.QtGui import QColor, QFont, QImage, QPainter

        width = max(2, int(project.width))
        height = max(2, int(project.height))
        image = QImage(width, height, QImage.Format.Format_RGBA8888)
        image.fill(QColor(0, 0, 0, 0))

        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        font = QFont("Arial", clip.font_size)
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        painter.setFont(font)

        color = QColor(clip.color) if clip.color else QColor("#ffffff")
        painter.setPen(color)

        x = int(clip.position_x * width)
        y = int(clip.position_y * height)

        painter.drawText(x, y, clip.content or "Text")
        painter.end()

        buffer = BytesIO()
        image.save(buffer, "PNG")
        frame_bytes = buffer.getvalue()

        return PreviewFrameResult(frame_bytes=frame_bytes, message=clip.content or "Text")
