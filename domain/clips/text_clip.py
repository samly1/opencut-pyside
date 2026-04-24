from __future__ import annotations

from dataclasses import dataclass

from app.domain.clips.base_clip import BaseClip


@dataclass(slots=True)
class TextClip(BaseClip):
    content: str = ""
    font_size: int = 48
    color: str = "#ffffff"
    position_x: float = 0.5
    position_y: float = 0.5
