from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class InterpolationType(Enum):
    LINEAR = "linear"
    EASE_IN = "ease_in"
    EASE_OUT = "ease_out"
    EASE_IN_OUT = "ease_in_out"
    HOLD = "hold"


@dataclass(slots=True)
class Keyframe:
    time: float
    value: float
    interpolation: InterpolationType = InterpolationType.LINEAR


@dataclass(slots=True)
class KeyframeTrack:
    property_name: str
    keyframes: list[Keyframe] = field(default_factory=list)

    def value_at(self, time: float) -> float | None:
        if not self.keyframes:
            return None

        sorted_keyframes = sorted(self.keyframes, key=lambda kf: kf.time)

        if time <= sorted_keyframes[0].time:
            return sorted_keyframes[0].value
        if time >= sorted_keyframes[-1].time:
            return sorted_keyframes[-1].value

        for i in range(len(sorted_keyframes) - 1):
            kf_a = sorted_keyframes[i]
            kf_b = sorted_keyframes[i + 1]
            if kf_a.time <= time <= kf_b.time:
                return self._interpolate(kf_a, kf_b, time)

        return sorted_keyframes[-1].value

    def add_keyframe(self, keyframe: Keyframe) -> None:
        self.keyframes = [kf for kf in self.keyframes if abs(kf.time - keyframe.time) > 1e-6]
        self.keyframes.append(keyframe)
        self.keyframes.sort(key=lambda kf: kf.time)

    def remove_keyframe_at(self, time: float, tolerance: float = 1e-6) -> bool:
        original_count = len(self.keyframes)
        self.keyframes = [kf for kf in self.keyframes if abs(kf.time - time) > tolerance]
        return len(self.keyframes) < original_count

    @staticmethod
    def _interpolate(kf_a: Keyframe, kf_b: Keyframe, time: float) -> float:
        if kf_a.interpolation == InterpolationType.HOLD:
            return kf_a.value

        span = kf_b.time - kf_a.time
        if span <= 0:
            return kf_a.value

        t = (time - kf_a.time) / span

        if kf_a.interpolation == InterpolationType.EASE_IN:
            t = t * t
        elif kf_a.interpolation == InterpolationType.EASE_OUT:
            t = 1.0 - (1.0 - t) * (1.0 - t)
        elif kf_a.interpolation == InterpolationType.EASE_IN_OUT:
            t = 3.0 * t * t - 2.0 * t * t * t

        return kf_a.value + (kf_b.value - kf_a.value) * t
