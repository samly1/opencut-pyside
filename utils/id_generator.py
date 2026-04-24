from __future__ import annotations

from uuid import uuid4


def generate_id(prefix: str = "") -> str:
    hex_id = uuid4().hex[:12]
    if prefix:
        return f"{prefix}_{hex_id}"
    return hex_id


def generate_clip_id() -> str:
    return generate_id("clip")


def generate_track_id() -> str:
    return generate_id("track")


def generate_media_id() -> str:
    return generate_id("media")


def generate_project_id() -> str:
    return generate_id("proj")


def generate_marker_id() -> str:
    return generate_id("marker")
