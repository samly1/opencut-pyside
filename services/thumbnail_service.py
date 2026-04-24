from __future__ import annotations

from pathlib import Path

from app.domain.clips.base_clip import BaseClip
from app.domain.clips.image_clip import ImageClip
from app.domain.clips.video_clip import VideoClip
from app.domain.media_asset import MediaAsset
from app.domain.project import Project
from app.infrastructure.ffmpeg_gateway import FFmpegGateway


class ThumbnailService:
    def __init__(
        self,
        ffmpeg_gateway: FFmpegGateway | None = None,
        cache_root: Path | None = None,
    ) -> None:
        self._ffmpeg_gateway = ffmpeg_gateway or FFmpegGateway()
        self._cache_root = cache_root or (Path.home() / ".opencut-pyside" / "cache" / "thumbnails")
        self._memory_cache: dict[str, bytes] = {}

    def get_thumbnail_bytes(
        self,
        project: Project,
        clip: BaseClip,
        project_path: str | None = None,
    ) -> bytes | None:
        if not isinstance(clip, (VideoClip, ImageClip)):
            return None

        media_asset = self._find_media_asset(project, clip.media_id)
        if media_asset is None:
            return None

        project_root = self._project_root(project_path)
        media_path = self._resolve_media_path(media_asset.file_path, project_root)
        if not media_path.exists() or not media_path.is_file():
            return None

        source_time = self._thumbnail_source_time(clip, media_asset)
        cache_path = self._cache_path(media_asset.media_id, source_time)
        cache_key = str(cache_path)

        cached = self._memory_cache.get(cache_key)
        if cached is not None:
            return cached

        if cache_path.exists() and cache_path.is_file():
            try:
                cached_bytes = cache_path.read_bytes()
            except OSError:
                cached_bytes = None
            if cached_bytes:
                self._memory_cache[cache_key] = cached_bytes
                return cached_bytes

        if isinstance(clip, ImageClip) or media_asset.media_type.lower() == "image":
            try:
                image_bytes = media_path.read_bytes()
            except OSError:
                return None
            if not image_bytes:
                return None
            self._persist_cache(cache_path, image_bytes)
            self._memory_cache[cache_key] = image_bytes
            return image_bytes

        frame_bytes = self._ffmpeg_gateway.extract_frame_png(str(media_path), source_time)
        if frame_bytes is None:
            return None

        self._persist_cache(cache_path, frame_bytes)
        self._memory_cache[cache_key] = frame_bytes
        return frame_bytes

    def clear_memory_cache(self) -> None:
        self._memory_cache.clear()

    def _persist_cache(self, cache_path: Path, payload: bytes) -> None:
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(payload)
        except OSError:
            return

    @staticmethod
    def _find_media_asset(project: Project, media_id: str | None) -> MediaAsset | None:
        if media_id is None:
            return None
        for media_asset in project.media_items:
            if media_asset.media_id == media_id:
                return media_asset
        return None

    @staticmethod
    def _thumbnail_source_time(clip: BaseClip, media_asset: MediaAsset) -> float:
        midpoint = clip.source_start + max(clip.duration, 0.0) * 0.5
        source_time = max(clip.source_start, midpoint)
        if clip.source_end is not None:
            source_time = min(source_time, clip.source_end)
        if media_asset.duration_seconds is not None and media_asset.duration_seconds > 0:
            source_time = min(source_time, max(0.0, media_asset.duration_seconds - 0.001))
        return max(0.0, source_time)

    def _cache_path(self, media_id: str, source_time: float) -> Path:
        normalized_media_id = media_id.strip() or "unknown"
        time_millis = int(round(max(0.0, source_time) * 1000.0))
        return self._cache_root / normalized_media_id / f"{time_millis}.png"

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
