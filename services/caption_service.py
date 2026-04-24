from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True, frozen=True)
class CaptionSegment:
    start_seconds: float
    end_seconds: float
    text: str

    @property
    def duration_seconds(self) -> float:
        return max(0.0, self.end_seconds - self.start_seconds)


class CaptionService:
    _TIME_RANGE_MARKER = "-->"
    _TIMESTAMP_RE = re.compile(r"^(?:(\d+):)?(\d{1,2}):(\d{2})(?:[.,](\d{1,3}))?$")

    def parse_file(self, file_path: str) -> list[CaptionSegment]:
        source_path = Path(file_path).expanduser().resolve()
        raw_text = source_path.read_text(encoding="utf-8")

        suffix = source_path.suffix.lower()
        if suffix == ".srt":
            return self.parse_srt(raw_text)
        if suffix == ".vtt":
            return self.parse_vtt(raw_text)
        raise ValueError(f"Unsupported subtitle file format: '{source_path.suffix}'")

    def parse_srt(self, text: str) -> list[CaptionSegment]:
        lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        blocks = self._split_blocks(lines)
        segments: list[CaptionSegment] = []
        for block in blocks:
            segment = self._segment_from_block(block)
            if segment is not None:
                segments.append(segment)
        return segments

    def parse_vtt(self, text: str) -> list[CaptionSegment]:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = normalized.split("\n")
        if lines and lines[0].lstrip("\ufeff").startswith("WEBVTT"):
            lines = lines[1:]
        blocks = self._split_blocks(lines)

        segments: list[CaptionSegment] = []
        for block in blocks:
            if not block:
                continue
            if block[0].strip().upper().startswith("NOTE"):
                continue
            segment = self._segment_from_block(block)
            if segment is not None:
                segments.append(segment)
        return segments

    @staticmethod
    def _split_blocks(lines: list[str]) -> list[list[str]]:
        blocks: list[list[str]] = []
        current: list[str] = []
        for raw_line in lines:
            line = raw_line.rstrip("\n")
            if line.strip():
                current.append(line)
                continue
            if current:
                blocks.append(current)
                current = []
        if current:
            blocks.append(current)
        return blocks

    def _segment_from_block(self, block: list[str]) -> CaptionSegment | None:
        time_line_index = self._time_line_index(block)
        if time_line_index < 0:
            return None

        start_seconds, end_seconds = self._parse_time_range(block[time_line_index])
        if end_seconds <= start_seconds:
            return None

        text_lines = block[time_line_index + 1 :]
        text = self._normalize_caption_text(text_lines)
        if not text:
            return None

        return CaptionSegment(start_seconds=start_seconds, end_seconds=end_seconds, text=text)

    def _time_line_index(self, block: list[str]) -> int:
        if not block:
            return -1
        if self._TIME_RANGE_MARKER in block[0]:
            return 0
        if len(block) > 1 and self._TIME_RANGE_MARKER in block[1]:
            return 1
        return -1

    def _parse_time_range(self, time_line: str) -> tuple[float, float]:
        if self._TIME_RANGE_MARKER not in time_line:
            raise ValueError(f"Invalid subtitle timing line: '{time_line}'")
        start_raw, end_raw = time_line.split(self._TIME_RANGE_MARKER, maxsplit=1)
        start_seconds = self._parse_timestamp(start_raw.strip().split(" ", maxsplit=1)[0])
        end_seconds = self._parse_timestamp(end_raw.strip().split(" ", maxsplit=1)[0])
        return start_seconds, end_seconds

    def _parse_timestamp(self, token: str) -> float:
        match = self._TIMESTAMP_RE.match(token)
        if match is None:
            raise ValueError(f"Invalid subtitle timestamp: '{token}'")

        hours_part, minutes_part, seconds_part, milliseconds_part = match.groups()
        hours = int(hours_part) if hours_part is not None else 0
        minutes = int(minutes_part)
        seconds = int(seconds_part)
        milliseconds = int((milliseconds_part or "0").ljust(3, "0")[:3])
        return (hours * 3600.0) + (minutes * 60.0) + seconds + (milliseconds / 1000.0)

    @staticmethod
    def _normalize_caption_text(lines: list[str]) -> str:
        compact_lines: list[str] = []
        for line in lines:
            cleaned = line.strip()
            if cleaned:
                compact_lines.append(cleaned)
        return "\n".join(compact_lines).strip()
