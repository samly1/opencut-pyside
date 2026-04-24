from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class CaptionEntry:
    index: int
    start_seconds: float
    end_seconds: float
    text: str


@dataclass(slots=True)
class CaptionTrack:
    entries: list[CaptionEntry] = field(default_factory=list)

    def entry_at(self, time_seconds: float) -> CaptionEntry | None:
        for entry in self.entries:
            if entry.start_seconds <= time_seconds <= entry.end_seconds:
                return entry
        return None

    def entries_in_range(self, start: float, end: float) -> list[CaptionEntry]:
        return [
            e for e in self.entries
            if e.end_seconds >= start and e.start_seconds <= end
        ]


class CaptionService:
    def load_srt(self, file_path: str) -> CaptionTrack:
        source_path = Path(file_path).expanduser().resolve()
        raw_text = source_path.read_text(encoding="utf-8", errors="replace")
        entries = self._parse_srt(raw_text)
        return CaptionTrack(entries=entries)

    def save_srt(self, caption_track: CaptionTrack, file_path: str) -> str:
        target_path = Path(file_path).expanduser().resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)

        lines: list[str] = []
        for entry in caption_track.entries:
            lines.append(str(entry.index))
            lines.append(f"{self._format_srt_time(entry.start_seconds)} --> {self._format_srt_time(entry.end_seconds)}")
            lines.append(entry.text)
            lines.append("")

        target_path.write_text("\n".join(lines), encoding="utf-8")
        return str(target_path)

    def _parse_srt(self, raw_text: str) -> list[CaptionEntry]:
        entries: list[CaptionEntry] = []
        blocks = re.split(r"\n\s*\n", raw_text.strip())

        for block in blocks:
            block_lines = block.strip().splitlines()
            if len(block_lines) < 3:
                continue

            try:
                index = int(block_lines[0].strip())
            except ValueError:
                continue

            time_match = re.match(
                r"(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})",
                block_lines[1].strip(),
            )
            if time_match is None:
                continue

            start_seconds = self._parse_srt_time(time_match.group(1))
            end_seconds = self._parse_srt_time(time_match.group(2))
            text = "\n".join(block_lines[2:])

            entries.append(CaptionEntry(
                index=index,
                start_seconds=start_seconds,
                end_seconds=end_seconds,
                text=text,
            ))

        return entries

    @staticmethod
    def _parse_srt_time(time_str: str) -> float:
        normalized = time_str.replace(",", ".")
        parts = normalized.split(":")
        if len(parts) != 3:
            return 0.0

        try:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = float(parts[2])
        except ValueError:
            return 0.0

        return hours * 3600.0 + minutes * 60.0 + seconds

    @staticmethod
    def _format_srt_time(total_seconds: float) -> str:
        total_seconds = max(0.0, total_seconds)
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = total_seconds % 60
        milliseconds = int((seconds - int(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{int(seconds):02d},{milliseconds:03d}"
