from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class MarkerColor(Enum):
    RED = "red"
    GREEN = "green"
    BLUE = "blue"
    YELLOW = "yellow"
    ORANGE = "orange"
    PURPLE = "purple"
    CYAN = "cyan"
    WHITE = "white"


@dataclass(slots=True)
class Marker:
    marker_id: str
    time: float
    name: str = ""
    color: MarkerColor = MarkerColor.BLUE
    comment: str = ""


@dataclass(slots=True)
class MarkerList:
    markers: list[Marker] = field(default_factory=list)

    def add_marker(self, marker: Marker) -> None:
        self.markers.append(marker)
        self.markers.sort(key=lambda m: m.time)

    def remove_marker(self, marker_id: str) -> bool:
        original_count = len(self.markers)
        self.markers = [m for m in self.markers if m.marker_id != marker_id]
        return len(self.markers) < original_count

    def find_marker(self, marker_id: str) -> Marker | None:
        for marker in self.markers:
            if marker.marker_id == marker_id:
                return marker
        return None

    def markers_in_range(self, start: float, end: float) -> list[Marker]:
        return [m for m in self.markers if start <= m.time <= end]

    def nearest_marker(self, time: float) -> Marker | None:
        if not self.markers:
            return None
        return min(self.markers, key=lambda m: abs(m.time - time))

    def next_marker(self, time: float) -> Marker | None:
        for marker in self.markers:
            if marker.time > time + 1e-6:
                return marker
        return None

    def previous_marker(self, time: float) -> Marker | None:
        result: Marker | None = None
        for marker in self.markers:
            if marker.time < time - 1e-6:
                result = marker
            else:
                break
        return result
