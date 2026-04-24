from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SelectionState:
    selected_clip_id: str | None = None
