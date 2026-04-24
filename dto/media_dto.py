from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class MediaImportRequest:
    file_paths: list[str]


@dataclass(slots=True, frozen=True)
class MediaImportResult:
    imported_count: int
    skipped_count: int
    errors: list[str]


@dataclass(slots=True, frozen=True)
class MediaInfo:
    media_id: str
    name: str
    file_path: str
    media_type: str
    duration_seconds: float | None
    file_size_bytes: int | None
