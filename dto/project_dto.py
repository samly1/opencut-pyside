from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class ProjectSummary:
    project_id: str
    name: str
    width: int
    height: int
    fps: float
    track_count: int
    clip_count: int
    total_duration: float


@dataclass(slots=True, frozen=True)
class NewProjectRequest:
    name: str = "Untitled Project"
    width: int = 1920
    height: int = 1080
    fps: float = 30.0


@dataclass(slots=True, frozen=True)
class ProjectSettings:
    name: str
    width: int
    height: int
    fps: float
    version: str = "0.1.0"
