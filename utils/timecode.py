from __future__ import annotations


def seconds_to_timecode(total_seconds: float, fps: float = 30.0) -> str:
    total_seconds = max(0.0, total_seconds)
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    secs = int(total_seconds % 60)
    safe_fps = fps if fps > 0 else 30.0
    frames = int((total_seconds % 1.0) * safe_fps)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}:{frames:02d}"


def seconds_to_timestamp(total_seconds: float) -> str:
    total_seconds = max(0.0, total_seconds)
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    secs = total_seconds % 60
    milliseconds = int((secs - int(secs)) * 1000)

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{int(secs):02d}.{milliseconds:03d}"
    return f"{minutes:02d}:{int(secs):02d}.{milliseconds:03d}"


def timecode_to_seconds(timecode: str, fps: float = 30.0) -> float:
    parts = timecode.strip().split(":")
    if len(parts) == 4:
        try:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = int(parts[2])
            frames = int(parts[3])
        except ValueError:
            return 0.0
        safe_fps = fps if fps > 0 else 30.0
        return hours * 3600.0 + minutes * 60.0 + seconds + frames / safe_fps

    if len(parts) == 3:
        try:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = float(parts[2])
        except ValueError:
            return 0.0
        return hours * 3600.0 + minutes * 60.0 + seconds

    if len(parts) == 2:
        try:
            minutes = int(parts[0])
            seconds = float(parts[1])
        except ValueError:
            return 0.0
        return minutes * 60.0 + seconds

    try:
        return float(timecode)
    except ValueError:
        return 0.0


def format_duration_short(total_seconds: float) -> str:
    total_seconds = max(0.0, total_seconds)
    minutes = int(total_seconds // 60)
    secs = int(total_seconds % 60)

    if minutes >= 60:
        hours = minutes // 60
        minutes = minutes % 60
        return f"{hours}h {minutes}m {secs}s"
    if minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def snap_to_frame(time_seconds: float, fps: float) -> float:
    safe_fps = fps if fps > 0 else 30.0
    frame_index = round(time_seconds * safe_fps)
    return frame_index / safe_fps
