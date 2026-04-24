from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ExportResult:
    output_path: str
    warnings: list[str] = field(default_factory=list)
