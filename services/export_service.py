from __future__ import annotations

import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from app.domain.clips.audio_clip import AudioClip
from app.domain.clips.base_clip import BaseClip
from app.domain.clips.image_clip import ImageClip
from app.domain.clips.text_clip import TextClip
from app.domain.clips.video_clip import VideoClip
from app.domain.media_asset import MediaAsset
from app.domain.project import Project
from app.dto.export_dto import ExportResult

ProgressCallback = Callable[[float, str], None]


@dataclass(slots=True)
class _PreparedClip:
    clip: BaseClip
    input_index: int
    placeholder: bool
    source_start: float
    source_end: float


class ExportService:
    _AUDIO_SAMPLE_RATE = 48_000
    _VIDEO_CODEC = "libx264"
    _VIDEO_PRESET = "veryfast"
    _VIDEO_CRF = "23"
    _AUDIO_CODEC = "aac"
    _AUDIO_BITRATE = "192k"

    def __init__(self, ffmpeg_executable: str | None = None, timeout_seconds: float | None = None) -> None:
        self._ffmpeg_executable = self._resolve_ffmpeg_executable(ffmpeg_executable)
        self._timeout_seconds = timeout_seconds

    def export_project(
        self,
        project: Project,
        output_path: str,
        project_path: str | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> ExportResult:
        if project is None:
            raise ValueError("No active project to export.")
        if not output_path or not output_path.strip():
            raise ValueError("An export output path is required.")
        if project.width <= 0 or project.height <= 0:
            raise ValueError("Project resolution must be greater than zero.")
        if project.fps <= 0:
            raise ValueError("Project FPS must be greater than zero.")
        if not any(track.clips for track in project.timeline.tracks):
            raise ValueError("Project has no clips to export.")

        target_path = self._normalize_output_path(output_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        project_root = self._project_root(project_path)
        total_duration = max(project.timeline.total_duration(), 0.1)

        warnings: list[str] = []
        self._emit_progress(progress_callback, 0.0, "Preparing export")
        command = self._build_ffmpeg_command(project, target_path, warnings, project_root)
        self._emit_progress(progress_callback, 5.0, "Launching FFmpeg")
        self._run_ffmpeg(command, total_duration, progress_callback)
        self._emit_progress(progress_callback, 100.0, "Export complete")
        return ExportResult(output_path=str(target_path), warnings=warnings)

    def _build_ffmpeg_command(
        self,
        project: Project,
        target_path: Path,
        warnings: list[str],
        project_root: Path | None,
    ) -> list[str]:
        duration = max(project.timeline.total_duration(), 0.1)
        fps = project.fps if project.fps > 0 else 30.0

        command = [
            self._ffmpeg_executable,
            "-hide_banner",
            "-nostdin",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=black:s={project.width}x{project.height}:r={fps:.6f}:d={duration:.6f}",
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=r={self._AUDIO_SAMPLE_RATE}:cl=stereo:d={duration:.6f}",
        ]

        visual_inputs: list[_PreparedClip] = []
        audio_inputs: list[_PreparedClip] = []
        input_index = 2
        skipped_text_clips = 0

        for track in project.timeline.tracks:
            for clip in track.sorted_clips():
                if isinstance(clip, TextClip):
                    skipped_text_clips += 1
                    continue

                media_asset = self._resolve_media_asset(project, clip.media_id)
                if isinstance(clip, (VideoClip, ImageClip)):
                    prepared_clip, input_index = self._append_visual_input(
                        command,
                        input_index,
                        clip,
                        media_asset,
                        project,
                        project_root,
                        fps,
                        warnings,
                    )
                    visual_inputs.append(prepared_clip)
                    continue

                if isinstance(clip, AudioClip):
                    prepared_clip, input_index = self._append_audio_input(
                        command,
                        input_index,
                        clip,
                        media_asset,
                        project_root,
                        warnings,
                    )
                    audio_inputs.append(prepared_clip)

        if skipped_text_clips > 0:
            warnings.append(
                f"Skipped {skipped_text_clips} text clip(s); text rendering is not implemented in export yet."
            )

        filter_parts: list[str] = ["[0:v]format=rgba[basev]"]
        current_video_label = "basev"

        for clip_index, clip_source in enumerate(visual_inputs):
            source_label = f"{clip_source.input_index}:v"
            clip_label = f"v{clip_index}"
            overlay_label = f"ov{clip_index}"
            source_end = max(clip_source.source_end, clip_source.source_start + 0.001)

            filter_parts.append(
                f"[{source_label}]"
                f"trim=start={clip_source.source_start:.6f}:end={source_end:.6f},"
                f"setpts=PTS-STARTPTS,"
                f"scale={project.width}:{project.height}:force_original_aspect_ratio=decrease,"
                f"pad={project.width}:{project.height}:(ow-iw)/2:(oh-ih)/2,"
                f"fps={fps:.6f},"
                f"format=rgba,"
                f"setpts=PTS-STARTPTS+{max(0.0, clip_source.clip.timeline_start):.6f}/TB"
                f"[{clip_label}]"
            )
            filter_parts.append(f"[{current_video_label}][{clip_label}]overlay=eof_action=pass:repeatlast=0[{overlay_label}]")
            current_video_label = overlay_label

        audio_output_label = "1:a"
        if audio_inputs:
            audio_stream_labels: list[str] = []
            for clip_index, clip_source in enumerate(audio_inputs):
                source_label = f"{clip_source.input_index}:a"
                audio_label = f"a{clip_index}"
                delay_ms = int(round(max(0.0, clip_source.clip.timeline_start) * 1000.0))
                volume_filter = ""
                if isinstance(clip_source.clip, AudioClip) and abs(clip_source.clip.gain_db) > 1e-9:
                    gain_factor = 10 ** (clip_source.clip.gain_db / 20.0)
                    volume_filter = f"volume={gain_factor:.6f},"
                source_end = max(clip_source.source_end, clip_source.source_start + 0.001)

                filter_parts.append(
                    f"[{source_label}]"
                    f"aformat=channel_layouts=stereo,"
                    f"aresample={self._AUDIO_SAMPLE_RATE},"
                    f"atrim=start={clip_source.source_start:.6f}:end={source_end:.6f},"
                    f"asetpts=PTS-STARTPTS,"
                    f"{volume_filter}"
                    f"adelay={delay_ms}|{delay_ms}"
                    f"[{audio_label}]"
                )
                audio_stream_labels.append(f"[{audio_label}]")

            amix_input_labels = "[1:a]" + "".join(audio_stream_labels)
            filter_parts.append(
                f"{amix_input_labels}amix=inputs={len(audio_inputs) + 1}:normalize=0:duration=longest[aout]"
            )
            audio_output_label = "aout"

        command.extend(
            [
                "-filter_complex",
                ";".join(filter_parts),
                "-map",
                f"[{current_video_label}]",
                "-map",
                audio_output_label if audio_output_label == "1:a" else f"[{audio_output_label}]",
                "-c:v",
                self._VIDEO_CODEC,
                "-preset",
                self._VIDEO_PRESET,
                "-crf",
                self._VIDEO_CRF,
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                self._AUDIO_CODEC,
                "-b:a",
                self._AUDIO_BITRATE,
                "-progress",
                "pipe:1",
                "-movflags",
                "+faststart",
                str(target_path),
            ]
        )
        return command

    def _append_visual_input(
        self,
        command: list[str],
        input_index: int,
        clip: BaseClip,
        media_asset: MediaAsset | None,
        project: Project,
        project_root: Path | None,
        fps: float,
        warnings: list[str],
    ) -> tuple[_PreparedClip, int]:
        duration = max(clip.duration, 0.001)
        source_start, source_end = self._clip_source_bounds(clip, placeholder=media_asset is None)

        if not self._media_file_exists(media_asset, project_root):
            warnings.append(f"Missing media for clip '{clip.name}'; using placeholder video.")
            command.extend(
                [
                    "-f",
                    "lavfi",
                    "-i",
                    f"color=c=gray:s={project.width}x{project.height}:r={fps:.6f}:d={duration:.6f}",
                ]
            )
            return _PreparedClip(
                clip=clip,
                input_index=input_index,
                placeholder=True,
                source_start=0.0,
                source_end=duration,
            ), input_index + 1

        media_path = self._resolve_media_path(media_asset.file_path, project_root)
        if isinstance(clip, ImageClip):
            command.extend(["-loop", "1", "-i", str(media_path)])
        else:
            command.extend(["-i", str(media_path)])
        return _PreparedClip(
            clip=clip,
            input_index=input_index,
            placeholder=False,
            source_start=source_start,
            source_end=source_end,
        ), input_index + 1

    def _append_audio_input(
        self,
        command: list[str],
        input_index: int,
        clip: AudioClip,
        media_asset: MediaAsset | None,
        project_root: Path | None,
        warnings: list[str],
    ) -> tuple[_PreparedClip, int]:
        duration = max(clip.duration, 0.001)
        source_start, source_end = self._clip_source_bounds(clip, placeholder=media_asset is None)

        if not self._media_file_exists(media_asset, project_root):
            warnings.append(f"Missing media for clip '{clip.name}'; using placeholder audio.")
            command.extend(
                [
                    "-f",
                    "lavfi",
                    "-i",
                    f"anullsrc=r={self._AUDIO_SAMPLE_RATE}:cl=stereo:d={duration:.6f}",
                ]
            )
            return _PreparedClip(
                clip=clip,
                input_index=input_index,
                placeholder=True,
                source_start=0.0,
                source_end=duration,
            ), input_index + 1

        media_path = self._resolve_media_path(media_asset.file_path, project_root)
        command.extend(["-i", str(media_path)])
        return _PreparedClip(
            clip=clip,
            input_index=input_index,
            placeholder=False,
            source_start=source_start,
            source_end=source_end,
        ), input_index + 1

    @staticmethod
    def _project_root(project_path: str | None) -> Path | None:
        if project_path is None or not project_path.strip():
            return None

        resolved_path = Path(project_path).expanduser().resolve()
        if resolved_path.is_dir():
            return resolved_path
        return resolved_path.parent

    @staticmethod
    def _clip_source_bounds(clip: BaseClip, placeholder: bool) -> tuple[float, float]:
        duration = max(clip.duration, 0.001)
        if placeholder:
            return 0.0, duration

        source_start = max(0.0, clip.source_start)
        source_end = clip.source_end
        if source_end is None or source_end <= source_start:
            source_end = source_start + duration
        return source_start, source_end

    def _resolve_media_asset(self, project: Project, media_id: str | None) -> MediaAsset | None:
        if media_id is None:
            return None
        for media_asset in project.media_items:
            if media_asset.media_id == media_id:
                return media_asset
        return None

    @staticmethod
    def _media_file_exists(media_asset: MediaAsset | None, project_root: Path | None) -> bool:
        if media_asset is None or not media_asset.file_path:
            return False
        media_path = ExportService._resolve_media_path(media_asset.file_path, project_root)
        return media_path.exists() and media_path.is_file()

    @staticmethod
    def _resolve_media_path(file_path: str, project_root: Path | None) -> Path:
        raw_path = Path(file_path).expanduser()
        if raw_path.is_absolute():
            return raw_path.resolve()

        if project_root is not None:
            return (project_root / raw_path).resolve()

        return raw_path.resolve()

    def _normalize_output_path(self, output_path: str) -> Path:
        normalized_path = Path(output_path).expanduser()
        if normalized_path.suffix.lower() != ".mp4":
            normalized_path = normalized_path.with_suffix(".mp4")
        return normalized_path.resolve()

    def _run_ffmpeg(
        self,
        command: list[str],
        duration_seconds: float,
        progress_callback: ProgressCallback | None,
    ) -> None:
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except OSError as exc:
            raise OSError(f"Unable to run FFmpeg: {exc}") from exc

        stderr_chunks: list[str] = []
        progress_thread = threading.Thread(
            target=self._consume_ffmpeg_progress,
            args=(process.stdout, duration_seconds, progress_callback),
            daemon=True,
        )
        stderr_thread = threading.Thread(
            target=self._drain_stream,
            args=(process.stderr, stderr_chunks),
            daemon=True,
        )
        progress_thread.start()
        stderr_thread.start()

        start_time = time.monotonic()
        try:
            if self._timeout_seconds is None:
                process.wait()
            else:
                while True:
                    try:
                        process.wait(timeout=0.25)
                        break
                    except subprocess.TimeoutExpired as timeout_exc:
                        if time.monotonic() - start_time > self._timeout_seconds:
                            process.kill()
                            process.wait()
                            raise RuntimeError(
                                f"FFmpeg export timed out after {self._timeout_seconds} seconds."
                            ) from timeout_exc
        except OSError as exc:
            process.kill()
            process.wait()
            raise OSError(f"Unable to run FFmpeg: {exc}") from exc
        finally:
            progress_thread.join()
            stderr_thread.join()

        if process.returncode != 0:
            stderr_text = "".join(stderr_chunks).strip()
            message = stderr_text or f"FFmpeg exited with code {process.returncode}"
            raise RuntimeError(message)

    @staticmethod
    def _consume_ffmpeg_progress(
        stdout: TextIO | None,
        duration_seconds: float,
        progress_callback: ProgressCallback | None,
    ) -> None:
        if stdout is None:
            return

        last_reported_percent: float | None = None
        for raw_line in stdout:
            line = raw_line.strip()
            if not line or "=" not in line:
                continue

            key, value = line.split("=", 1)
            if key == "progress":
                if value == "end":
                    ExportService._emit_progress(progress_callback, 99.9, "Finalizing export")
                    return
                continue

            elapsed_seconds = ExportService._parse_ffmpeg_progress_time(key, value)
            if elapsed_seconds is None:
                continue

            percent = ExportService._percent_from_time(elapsed_seconds, duration_seconds)
            if last_reported_percent is not None and percent <= last_reported_percent + 0.5:
                continue
            last_reported_percent = percent
            ExportService._emit_progress(progress_callback, percent, "Rendering")

    @staticmethod
    def _parse_ffmpeg_progress_time(key: str, value: str) -> float | None:
        if key == "out_time":
            return ExportService._parse_ffmpeg_timecode(value)
        if key in {"out_time_us", "out_time_ms"}:
            try:
                return int(value) / 1_000_000.0
            except ValueError:
                return None
        return None

    @staticmethod
    def _parse_ffmpeg_timecode(timecode: str) -> float | None:
        parts = timecode.strip().split(":")
        if len(parts) != 3:
            return None

        try:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = float(parts[2])
        except ValueError:
            return None
        return (hours * 3600.0) + (minutes * 60.0) + seconds

    @staticmethod
    def _percent_from_time(elapsed_seconds: float, duration_seconds: float) -> float:
        if duration_seconds <= 0:
            return 0.0

        percent = (elapsed_seconds / duration_seconds) * 100.0
        return max(0.0, min(percent, 99.9))

    @staticmethod
    def _emit_progress(progress_callback: ProgressCallback | None, percent: float, message: str) -> None:
        if progress_callback is None:
            return
        progress_callback(max(0.0, min(percent, 100.0)), message)

    @staticmethod
    def _drain_stream(stream: TextIO | None, sink: list[str]) -> None:
        if stream is None:
            return
        for line in stream:
            sink.append(line)

    @staticmethod
    def _resolve_ffmpeg_executable(explicit_executable: str | None) -> str:
        if explicit_executable:
            return explicit_executable

        bin_dir = Path(__file__).resolve().parents[1] / "bin"
        candidate_names = ["ffmpeg.exe"] if sys.platform.startswith("win") else ["ffmpeg"]
        for name in candidate_names:
            candidate = bin_dir / name
            if candidate.exists():
                return str(candidate)

        for name in ("ffmpeg", "ffmpeg.exe"):
            system_executable = shutil.which(name)
            if system_executable is not None:
                return system_executable

        raise FileNotFoundError("ffmpeg executable was not found.")
