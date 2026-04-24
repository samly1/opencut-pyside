from __future__ import annotations


def clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(value, max_value))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * clamp(t, 0.0, 1.0)


def inverse_lerp(a: float, b: float, value: float) -> float:
    if abs(b - a) < 1e-12:
        return 0.0
    return clamp((value - a) / (b - a), 0.0, 1.0)


def remap(value: float, in_min: float, in_max: float, out_min: float, out_max: float) -> float:
    t = inverse_lerp(in_min, in_max, value)
    return lerp(out_min, out_max, t)


def snap_value(value: float, step: float) -> float:
    if step <= 0:
        return value
    return round(value / step) * step


def almost_equal(a: float, b: float, epsilon: float = 1e-6) -> bool:
    return abs(a - b) <= epsilon


def pixels_to_seconds(pixels: float, pixels_per_second: float) -> float:
    if pixels_per_second <= 0:
        return 0.0
    return pixels / pixels_per_second


def seconds_to_pixels(seconds: float, pixels_per_second: float) -> float:
    return seconds * pixels_per_second
