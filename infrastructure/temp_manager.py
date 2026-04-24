from __future__ import annotations

import atexit
import os
import shutil
import tempfile
from pathlib import Path


class TempManager:
    def __init__(self, prefix: str = "opencut-pyside-") -> None:
        self._prefix = prefix
        self._temp_dirs: list[Path] = []
        self._temp_files: list[Path] = []
        atexit.register(self.cleanup_all)

    def create_temp_dir(self, suffix: str = "") -> str:
        temp_dir = Path(tempfile.mkdtemp(prefix=self._prefix, suffix=suffix))
        self._temp_dirs.append(temp_dir)
        return str(temp_dir)

    def create_temp_file(self, suffix: str = "", directory: str | None = None) -> str:
        dir_path = directory if directory else None
        fd, temp_path = tempfile.mkstemp(prefix=self._prefix, suffix=suffix, dir=dir_path)
        os.close(fd)
        path = Path(temp_path)
        self._temp_files.append(path)
        return str(path)

    def cleanup_all(self) -> None:
        for temp_file in self._temp_files:
            try:
                if temp_file.exists():
                    temp_file.unlink(missing_ok=True)
            except OSError:
                pass
        self._temp_files.clear()

        for temp_dir in self._temp_dirs:
            try:
                if temp_dir.exists():
                    shutil.rmtree(temp_dir, ignore_errors=True)
            except OSError:
                pass
        self._temp_dirs.clear()

    def cleanup_file(self, file_path: str) -> bool:
        target = Path(file_path)
        try:
            if target.exists():
                target.unlink(missing_ok=True)
                self._temp_files = [p for p in self._temp_files if p != target]
                return True
        except OSError:
            pass
        return False

    def cleanup_dir(self, dir_path: str) -> bool:
        target = Path(dir_path)
        try:
            if target.exists():
                shutil.rmtree(target, ignore_errors=True)
                self._temp_dirs = [p for p in self._temp_dirs if p != target]
                return True
        except OSError:
            pass
        return False
