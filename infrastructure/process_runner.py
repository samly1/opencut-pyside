from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class ProcessResult:
    return_code: int
    stdout: str
    stderr: str

    @property
    def success(self) -> bool:
        return self.return_code == 0


class ProcessRunner:
    def __init__(self, timeout_seconds: float | None = None) -> None:
        self._timeout_seconds = timeout_seconds

    def run(
        self,
        command: list[str],
        timeout_seconds: float | None = None,
        cwd: str | None = None,
    ) -> ProcessResult:
        effective_timeout = timeout_seconds if timeout_seconds is not None else self._timeout_seconds

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=effective_timeout,
                cwd=cwd,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return ProcessResult(
                return_code=-1,
                stdout=exc.stdout or "" if isinstance(exc.stdout, str) else "",
                stderr=f"Process timed out after {effective_timeout} seconds",
            )
        except OSError as exc:
            return ProcessResult(
                return_code=-1,
                stdout="",
                stderr=str(exc),
            )

        return ProcessResult(
            return_code=result.returncode,
            stdout=result.stdout or "",
            stderr=result.stderr or "",
        )

    def run_check(
        self,
        command: list[str],
        timeout_seconds: float | None = None,
        cwd: str | None = None,
    ) -> ProcessResult:
        result = self.run(command, timeout_seconds=timeout_seconds, cwd=cwd)
        if not result.success:
            raise RuntimeError(
                f"Command failed with code {result.return_code}: {result.stderr}"
            )
        return result
