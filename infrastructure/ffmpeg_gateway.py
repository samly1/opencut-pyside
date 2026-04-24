from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _bundled_ffmpeg_candidates(bin_dir: Path) -> list[Path]:
    """Return possible bundled ffmpeg binaries for the current platform."""

    if sys.platform.startswith("win"):
        names = ["ffmpeg.exe"]
    else:
        names = ["ffmpeg"]
    return [bin_dir / name for name in names]


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
            logger.warning("ffmpeg OS error: %s", exc)
            return None
        except subprocess.SubprocessError as exc:
            logger.warning("ffmpeg subprocess error: %s", exc)
            return None

        if result.returncode != 0:
            stderr_text = result.stderr.decode("utf-8", errors="ignore").strip()
            logger.debug("ffmpeg failed (returncode=%s) cmd=%s stderr=%s", result.returncode, " ".join(command), stderr_text)
            return None

        if not result.stdout:
            logger.debug("ffmpeg produced no output for cmd=%s", " ".join(command))
            return None

        return bytes(result.stdout)

    @staticmethod
    def _resolve_ffmpeg_executable(explicit_executable: str | None) -> str:
        """Resolve the ffmpeg executable across Windows/macOS/Linux.

        Preference order:
            1. Explicit path passed in (if it exists).
            2. Explicit name resolvable via ``shutil.which``.
            3. Platform-appropriate bundled binary in ``<repo>/bin``.
            4. System ``ffmpeg`` / ``ffmpeg.exe`` on ``PATH``.
            5. Fallback string ``"ffmpeg"`` so callers can still fail gracefully.
        """

        if explicit_executable:
            explicit_path = Path(explicit_executable).expanduser()
            if explicit_path.exists():
                return str(explicit_path.resolve())

            system_explicit = shutil.which(explicit_executable)
            if system_explicit is not None:
                return system_explicit

            return explicit_executable

        bin_dir = Path(__file__).resolve().parents[1] / "bin"
        for candidate in _bundled_ffmpeg_candidates(bin_dir):
            if candidate.exists():
                return str(candidate)

        for name in ("ffmpeg", "ffmpeg.exe"):
            system_executable = shutil.which(name)
            if system_executable is not None:
                return system_executable

        return "ffmpeg"
