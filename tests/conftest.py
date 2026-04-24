"""Pytest bootstrap.

The repository is laid out so that the folder itself is the importable
``app`` package (``python -m app.main`` works when the *parent* directory
is on ``sys.path``). Tests expect the same import path, so we create a
temporary symlink (or ``.pth``-style mapping via ``sys.path``) that makes
``import app`` work regardless of where pytest was invoked from.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _ensure_app_import_path() -> None:
    # Create a staging directory with a symlink named ``app`` pointing at the
    # repo root so that ``import app`` resolves to this project's source tree.
    staging_dir = Path(tempfile.gettempdir()) / "opencut-pyside-test-root"
    staging_dir.mkdir(parents=True, exist_ok=True)
    symlink_path = staging_dir / "app"
    try:
        if not symlink_path.exists():
            symlink_path.symlink_to(REPO_ROOT, target_is_directory=True)
    except OSError:
        # Fallback for platforms without symlink permissions – copy path in directly.
        pass

    if str(staging_dir) not in sys.path:
        sys.path.insert(0, str(staging_dir))


def _ensure_offscreen_qt() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


_ensure_offscreen_qt()
_ensure_app_import_path()
