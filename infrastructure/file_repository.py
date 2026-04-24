from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class FileRepository:
    @staticmethod
    def read_text(file_path: str, encoding: str = "utf-8") -> str:
        source_path = Path(file_path).expanduser().resolve()
        return source_path.read_text(encoding=encoding)

    @staticmethod
    def write_text(file_path: str, content: str, encoding: str = "utf-8") -> str:
        target_path = Path(file_path).expanduser().resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding=encoding)
        return str(target_path)

    @staticmethod
    def read_bytes(file_path: str) -> bytes:
        source_path = Path(file_path).expanduser().resolve()
        return source_path.read_bytes()

    @staticmethod
    def write_bytes(file_path: str, content: bytes) -> str:
        target_path = Path(file_path).expanduser().resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(content)
        return str(target_path)

    @staticmethod
    def read_json(file_path: str) -> Any:
        raw_text = FileRepository.read_text(file_path)
        return json.loads(raw_text)

    @staticmethod
    def write_json(file_path: str, data: Any, indent: int = 2) -> str:
        content = json.dumps(data, indent=indent, ensure_ascii=True)
        return FileRepository.write_text(file_path, content)

    @staticmethod
    def exists(file_path: str) -> bool:
        return Path(file_path).expanduser().resolve().exists()

    @staticmethod
    def is_file(file_path: str) -> bool:
        return Path(file_path).expanduser().resolve().is_file()

    @staticmethod
    def is_directory(file_path: str) -> bool:
        return Path(file_path).expanduser().resolve().is_dir()

    @staticmethod
    def file_size(file_path: str) -> int:
        return Path(file_path).expanduser().resolve().stat().st_size

    @staticmethod
    def delete(file_path: str) -> bool:
        target_path = Path(file_path).expanduser().resolve()
        if not target_path.exists():
            return False
        target_path.unlink(missing_ok=True)
        return True

    @staticmethod
    def ensure_directory(dir_path: str) -> str:
        target_dir = Path(dir_path).expanduser().resolve()
        target_dir.mkdir(parents=True, exist_ok=True)
        return str(target_dir)

    @staticmethod
    def list_files(dir_path: str, pattern: str = "*") -> list[str]:
        target_dir = Path(dir_path).expanduser().resolve()
        if not target_dir.is_dir():
            return []
        return [str(p) for p in sorted(target_dir.glob(pattern)) if p.is_file()]
