from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True, frozen=True)
class MediaProbeResult:
    duration_seconds: float | None
    width: int | None
    height: int | None
    codec_name: str | None
    format_name: str | None
    bit_rate: int | None
    sample_rate: int | None
    channels: int | None


class FFprobeGateway:
    def __init__(self, ffprobe_executable: str | None = None, timeout_seconds: float = 8.0) -> None:
        self._ffprobe_executable = self._resolve_ffprobe_executable(ffprobe_executable)
        self._timeout_seconds = timeout_seconds
        self._is_available_cache: bool | None = None

    def is_available(self) -> bool:
        if self._is_available_cache is None:
            executable_path = Path(self._ffprobe_executable)
            self._is_available_cache = executable_path.exists() or shutil.which(self._ffprobe_executable) is not None
        return self._is_available_cache

    def probe(self, file_path: str) -> MediaProbeResult | None:
        if not self.is_available():
            return None

        try:
            source_path = Path(file_path).expanduser().resolve()
        except OSError:
            return None

        if not source_path.exists() or not source_path.is_file():
            return None

        command = [
            self._ffprobe_executable,
            "-hide_banner",
            "-loglevel", "error",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(source_path),
        ]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                check=False,
                timeout=self._timeout_seconds,
            )
        except (OSError, subprocess.SubprocessError):
            return None

        if result.returncode != 0 or not result.stdout:
            return None

        try:
            data = json.loads(result.stdout.decode("utf-8", errors="ignore"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

        return self._parse_probe_data(data)

    def probe_duration(self, file_path: str) -> float | None:
        probe_result = self.probe(file_path)
        if probe_result is None:
            return None
        return probe_result.duration_seconds

    @staticmethod
    def _parse_probe_data(data: dict) -> MediaProbeResult:
        format_info = data.get("format", {})
        streams = data.get("streams", [])

        duration_seconds: float | None = None
        width: int | None = None
        height: int | None = None
        codec_name: str | None = None
        format_name = format_info.get("format_name")
        bit_rate: int | None = None
        sample_rate: int | None = None
        channels: int | None = None

        raw_duration = format_info.get("duration")
        if raw_duration is not None:
            try:
                duration_seconds = float(raw_duration)
            except (ValueError, TypeError):
                pass

        raw_bit_rate = format_info.get("bit_rate")
        if raw_bit_rate is not None:
            try:
                bit_rate = int(raw_bit_rate)
            except (ValueError, TypeError):
                pass

        for stream in streams:
            codec_type = stream.get("codec_type", "")
            if codec_type == "video" and width is None:
                codec_name = stream.get("codec_name")
                try:
                    width = int(stream["width"])
                    height = int(stream["height"])
                except (KeyError, ValueError, TypeError):
                    pass
                if duration_seconds is None:
                    raw_stream_duration = stream.get("duration")
                    if raw_stream_duration is not None:
                        try:
                            duration_seconds = float(raw_stream_duration)
                        except (ValueError, TypeError):
                            pass

            if codec_type == "audio":
                if codec_name is None:
                    codec_name = stream.get("codec_name")
                raw_sample_rate = stream.get("sample_rate")
                if raw_sample_rate is not None:
                    try:
                        sample_rate = int(raw_sample_rate)
                    except (ValueError, TypeError):
                        pass
                raw_channels = stream.get("channels")
                if raw_channels is not None:
                    try:
                        channels = int(raw_channels)
                    except (ValueError, TypeError):
                        pass
                if duration_seconds is None:
                    raw_stream_duration = stream.get("duration")
                    if raw_stream_duration is not None:
                        try:
                            duration_seconds = float(raw_stream_duration)
                        except (ValueError, TypeError):
                            pass

        return MediaProbeResult(
            duration_seconds=duration_seconds,
            width=width,
            height=height,
            codec_name=codec_name,
            format_name=format_name,
            bit_rate=bit_rate,
            sample_rate=sample_rate,
            channels=channels,
        )

    @staticmethod
    def _resolve_ffprobe_executable(explicit_executable: str | None) -> str:
        if explicit_executable:
            explicit_path = Path(explicit_executable).expanduser()
            if explicit_path.exists():
                return str(explicit_path.resolve())

            system_explicit = shutil.which(explicit_executable)
            if system_explicit is not None:
                return system_explicit

            return explicit_executable

        bundled_executable = Path(__file__).resolve().parents[1] / "bin" / "ffprobe.exe"
        if bundled_executable.exists():
            return str(bundled_executable)

        system_executable = shutil.which("ffprobe")
        if system_executable is not None:
            return system_executable

        return "ffprobe"
