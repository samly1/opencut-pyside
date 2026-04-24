from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class FFmpegGateway:
    def __init__(self, ffmpeg_executable: str | None = None, timeout_seconds: float = 8.0) -> None:
        self._ffmpeg_executable = self._resolve_ffmpeg_executable(ffmpeg_executable)
        self._timeout_seconds = timeout_seconds
        self._is_available_cache: bool | None = None

    def is_available(self) -> bool:
        if self._is_available_cache is None:
            executable_path = Path(self._ffmpeg_executable)
            self._is_available_cache = executable_path.exists() or shutil.which(self._ffmpeg_executable) is not None
        return self._is_available_cache

    def extract_frame_png(self, file_path: str, time_seconds: float) -> bytes | None:
        if not self.is_available():
            return None

        try:
            source_path = Path(file_path).expanduser().resolve()
        except OSError:
            return None

        if not source_path.exists() or not source_path.is_file():
            return None

        safe_time = max(0.0, float(time_seconds))

        command = self._build_extract_frame_command(source_path, safe_time, seek_before_input=True)
        frame_bytes = self._run_ffmpeg(command)
        if frame_bytes is not None:
            return frame_bytes

        # Fallback seek order for files that decode better with post-input seeking.
        fallback_command = self._build_extract_frame_command(source_path, safe_time, seek_before_input=False)
        return self._run_ffmpeg(fallback_command)

    def _build_extract_frame_command(self, source_path: Path, time_seconds: float, seek_before_input: bool) -> list[str]:
        command = [self._ffmpeg_executable, "-hide_banner", "-loglevel", "error", "-nostdin"]
        if seek_before_input:
            command.extend(["-ss", f"{time_seconds:.6f}"])
        command.extend(["-i", str(source_path)])
        if not seek_before_input:
            command.extend(["-ss", f"{time_seconds:.6f}"])
        command.extend(
            [
                "-frames:v",
                "1",
                "-an",
                "-sn",
                "-dn",
                "-f",
                "image2pipe",
                "-vcodec",
                "png",
                "pipe:1",
            ]
        )
        return command

    def _run_ffmpeg(self, command: list[str]) -> bytes | None:
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                check=False,
                timeout=self._timeout_seconds,
            )
        except OSError as exc:
            print("FFMPEG OS ERROR:", exc)
            return None
        except subprocess.SubprocessError as exc:
            print("FFMPEG SUBPROCESS ERROR:", exc)
            return None

        if result.returncode != 0:
            stderr_text = result.stderr.decode("utf-8", errors="ignore").strip()
            print("FFMPEG FAILED:")
            print("COMMAND:", " ".join(command))
            print("STDERR:", stderr_text)
            return None

        if not result.stdout:
            print("FFMPEG EMPTY OUTPUT")
            return None

        return bytes(result.stdout)

    @staticmethod
    def _resolve_ffmpeg_executable(explicit_executable: str | None) -> str:
        bundled_executable = Path(__file__).resolve().parents[1] / "bin" / "ffmpeg.exe"
        if explicit_executable:
            explicit_path = Path(explicit_executable).expanduser()
            if explicit_path.exists():
                return str(explicit_path.resolve())

            system_explicit = shutil.which(explicit_executable)
            if system_explicit is not None:
                return system_explicit

            return explicit_executable

        if bundled_executable.exists():
            return str(bundled_executable)

        system_executable = shutil.which("ffmpeg")
        if system_executable is not None:
            return system_executable

        return "ffmpeg"
