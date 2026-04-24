from __future__ import annotations

import hashlib
from pathlib import Path

from app.infrastructure.ffmpeg_gateway import FFmpegGateway


class ThumbnailService:
    def __init__(
        self,
        ffmpeg_gateway: FFmpegGateway | None = None,
        cache_dir: str | None = None,
    ) -> None:
        self._ffmpeg_gateway = ffmpeg_gateway or FFmpegGateway()
        if cache_dir is not None:
            self._cache_dir = Path(cache_dir).expanduser().resolve()
        else:
            self._cache_dir = Path.home() / ".opencut-pyside" / "thumbnails"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory_cache: dict[str, bytes] = {}

    def get_thumbnail(self, file_path: str, time_seconds: float = 0.5) -> bytes | None:
        cache_key = self._cache_key(file_path, time_seconds)

        cached = self._memory_cache.get(cache_key)
        if cached is not None:
            return cached

        disk_path = self._cache_dir / f"{cache_key}.png"
        if disk_path.exists():
            try:
                image_bytes = disk_path.read_bytes()
                if image_bytes:
                    self._memory_cache[cache_key] = image_bytes
                    return image_bytes
            except OSError:
                pass

        image_bytes = self._ffmpeg_gateway.extract_frame_png(file_path, time_seconds)
        if image_bytes is None:
            return None

        self._memory_cache[cache_key] = image_bytes
        try:
            disk_path.write_bytes(image_bytes)
        except OSError:
            pass

        return image_bytes

    def clear_cache(self) -> None:
        self._memory_cache.clear()
        if self._cache_dir.exists():
            for child in self._cache_dir.iterdir():
                if child.suffix == ".png":
                    try:
                        child.unlink()
                    except OSError:
                        pass

    @staticmethod
    def _cache_key(file_path: str, time_seconds: float) -> str:
        resolved = str(Path(file_path).expanduser().resolve())
        raw = f"{resolved}@{time_seconds:.3f}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
