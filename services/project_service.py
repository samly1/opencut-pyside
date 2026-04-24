from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.domain.clips.audio_clip import AudioClip
from app.domain.clips.base_clip import BaseClip
from app.domain.clips.image_clip import ImageClip
from app.domain.clips.text_clip import TextClip
from app.domain.clips.video_clip import VideoClip
from app.domain.media_asset import MediaAsset
from app.domain.project import Project
from app.domain.timeline import Timeline
from app.domain.track import Track


class ProjectService:
    _FORMAT_VERSION = "1.0"

    def save_project(self, project: Project, file_path: str) -> str:
        target_path = Path(file_path).expanduser().resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)
        payload = self._project_to_dict(project)
        target_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
        return str(target_path)

    def load_project(self, file_path: str) -> Project:
        source_path = Path(file_path).expanduser().resolve()
        raw_text = source_path.read_text(encoding="utf-8")
        payload = json.loads(raw_text)
        if not isinstance(payload, dict):
            raise ValueError("Invalid project file: root JSON must be an object")
        return self._project_from_dict(payload)

    def _project_to_dict(self, project: Project) -> dict[str, Any]:
        return {
            "format_version": self._FORMAT_VERSION,
            "project_id": project.project_id,
            "name": project.name,
            "width": project.width,
            "height": project.height,
            "fps": project.fps,
            "version": project.version,
            "media_items": [self._media_asset_to_dict(media_asset) for media_asset in project.media_items],
            "timeline": self._timeline_to_dict(project.timeline),
        }

    def _project_from_dict(self, payload: dict[str, Any]) -> Project:
        timeline_data = payload.get("timeline")
        if not isinstance(timeline_data, dict):
            raise ValueError("Invalid project file: missing timeline object")

        media_items_data = payload.get("media_items", [])
        if not isinstance(media_items_data, list):
            raise ValueError("Invalid project file: media_items must be a list")

        return Project(
            project_id=self._read_str(payload, "project_id"),
            name=self._read_str(payload, "name"),
            width=self._read_int(payload, "width"),
            height=self._read_int(payload, "height"),
            fps=self._read_float(payload, "fps"),
            timeline=self._timeline_from_dict(timeline_data),
            media_items=[self._media_asset_from_dict(item) for item in media_items_data if isinstance(item, dict)],
            version=self._read_str(payload, "version", default="0.1.0"),
        )

    def _timeline_to_dict(self, timeline: Timeline) -> dict[str, Any]:
        return {
            "tracks": [self._track_to_dict(track) for track in timeline.tracks],
        }

    def _timeline_from_dict(self, payload: dict[str, Any]) -> Timeline:
        tracks_payload = payload.get("tracks", [])
        if not isinstance(tracks_payload, list):
            raise ValueError("Invalid project file: timeline.tracks must be a list")
        return Timeline(
            tracks=[self._track_from_dict(track_payload) for track_payload in tracks_payload if isinstance(track_payload, dict)],
        )

    def _track_to_dict(self, track: Track) -> dict[str, Any]:
        return {
            "track_id": track.track_id,
            "name": track.name,
            "track_type": track.track_type,
            "clips": [self._clip_to_dict(clip) for clip in track.clips],
        }

    def _track_from_dict(self, payload: dict[str, Any]) -> Track:
        track_id = self._read_str(payload, "track_id")
        clips_payload = payload.get("clips", [])
        if not isinstance(clips_payload, list):
            raise ValueError("Invalid project file: track.clips must be a list")

        return Track(
            track_id=track_id,
            name=self._read_str(payload, "name"),
            track_type=self._read_str(payload, "track_type"),
            clips=[self._clip_from_dict(clip_payload, track_id) for clip_payload in clips_payload if isinstance(clip_payload, dict)],
        )

    def _clip_to_dict(self, clip: BaseClip) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "clip_type": self._clip_type_name(clip),
            "clip_id": clip.clip_id,
            "name": clip.name,
            "track_id": clip.track_id,
            "timeline_start": clip.timeline_start,
            "duration": clip.duration,
            "media_id": clip.media_id,
            "source_start": clip.source_start,
            "source_end": clip.source_end,
            "opacity": clip.opacity,
            "is_locked": clip.is_locked,
            "is_muted": clip.is_muted,
        }

        if isinstance(clip, VideoClip):
            payload["playback_speed"] = clip.playback_speed
        elif isinstance(clip, AudioClip):
            payload["gain_db"] = clip.gain_db
        elif isinstance(clip, ImageClip):
            payload["scale"] = clip.scale
        elif isinstance(clip, TextClip):
            payload["content"] = clip.content
            payload["font_size"] = clip.font_size
            payload["color"] = clip.color
            payload["position_x"] = clip.position_x
            payload["position_y"] = clip.position_y
        return payload

    def _clip_from_dict(self, payload: dict[str, Any], track_id: str) -> BaseClip:
        clip_type = self._read_str(payload, "clip_type", default="video").lower()
        base_kwargs = {
            "clip_id": self._read_str(payload, "clip_id"),
            "name": self._read_str(payload, "name"),
            "track_id": track_id,
            "timeline_start": self._read_float(payload, "timeline_start"),
            "duration": self._read_float(payload, "duration"),
            "media_id": self._read_optional_str(payload, "media_id"),
            "source_start": self._read_float(payload, "source_start", default=0.0),
            "source_end": self._read_optional_float(payload, "source_end"),
            "opacity": self._read_float(payload, "opacity", default=1.0),
            "is_locked": self._read_bool(payload, "is_locked", default=False),
            "is_muted": self._read_bool(payload, "is_muted", default=False),
        }

        if clip_type == "video":
            return VideoClip(
                **base_kwargs,
                playback_speed=self._read_float(payload, "playback_speed", default=1.0),
            )
        if clip_type == "audio":
            return AudioClip(
                **base_kwargs,
                gain_db=self._read_float(payload, "gain_db", default=0.0),
            )
        if clip_type == "image":
            return ImageClip(
                **base_kwargs,
                scale=self._read_float(payload, "scale", default=1.0),
            )
        if clip_type == "text":
            return TextClip(
                **base_kwargs,
                content=self._read_str(payload, "content", default=""),
                font_size=self._read_int(payload, "font_size", default=48),
                color=self._read_str(payload, "color", default="#ffffff"),
                position_x=self._read_float(payload, "position_x", default=0.5),
                position_y=self._read_float(payload, "position_y", default=0.5),
            )
        raise ValueError(f"Invalid project file: unsupported clip_type '{clip_type}'")

    @staticmethod
    def _clip_type_name(clip: BaseClip) -> str:
        if isinstance(clip, VideoClip):
            return "video"
        if isinstance(clip, AudioClip):
            return "audio"
        if isinstance(clip, ImageClip):
            return "image"
        if isinstance(clip, TextClip):
            return "text"
        return "base"

    @staticmethod
    def _media_asset_to_dict(media_asset: MediaAsset) -> dict[str, Any]:
        return {
            "media_id": media_asset.media_id,
            "name": media_asset.name,
            "file_path": media_asset.file_path,
            "media_type": media_asset.media_type,
            "duration_seconds": media_asset.duration_seconds,
            "file_size_bytes": media_asset.file_size_bytes,
        }

    def _media_asset_from_dict(self, payload: dict[str, Any]) -> MediaAsset:
        return MediaAsset(
            media_id=self._read_str(payload, "media_id"),
            name=self._read_str(payload, "name"),
            file_path=self._read_str(payload, "file_path"),
            media_type=self._read_str(payload, "media_type"),
            duration_seconds=self._read_optional_float(payload, "duration_seconds"),
            file_size_bytes=self._read_optional_int(payload, "file_size_bytes"),
        )

    @staticmethod
    def _read_str(payload: dict[str, Any], key: str, default: str | None = None) -> str:
        value = payload.get(key, default)
        if isinstance(value, str):
            return value
        raise ValueError(f"Invalid project file: '{key}' must be a string")

    @staticmethod
    def _read_optional_str(payload: dict[str, Any], key: str) -> str | None:
        value = payload.get(key)
        if value is None:
            return None
        if isinstance(value, str):
            return value
        raise ValueError(f"Invalid project file: '{key}' must be a string or null")

    @staticmethod
    def _read_int(payload: dict[str, Any], key: str, default: int | None = None) -> int:
        value = payload.get(key, default)
        if isinstance(value, int):
            return value
        raise ValueError(f"Invalid project file: '{key}' must be an integer")

    @staticmethod
    def _read_optional_int(payload: dict[str, Any], key: str) -> int | None:
        value = payload.get(key)
        if value is None:
            return None
        if isinstance(value, int):
            return value
        raise ValueError(f"Invalid project file: '{key}' must be an integer or null")

    @staticmethod
    def _read_float(payload: dict[str, Any], key: str, default: float | None = None) -> float:
        value = payload.get(key, default)
        if isinstance(value, (int, float)):
            return float(value)
        raise ValueError(f"Invalid project file: '{key}' must be numeric")

    @staticmethod
    def _read_optional_float(payload: dict[str, Any], key: str) -> float | None:
        value = payload.get(key)
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        raise ValueError(f"Invalid project file: '{key}' must be numeric or null")

    @staticmethod
    def _read_bool(payload: dict[str, Any], key: str, default: bool = False) -> bool:
        value = payload.get(key, default)
        if isinstance(value, bool):
            return value
        raise ValueError(f"Invalid project file: '{key}' must be a boolean")
