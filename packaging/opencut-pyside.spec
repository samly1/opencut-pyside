# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for opencut-pyside.

Invoked via one of the ``packaging/build_*`` scripts or the GitHub Actions
``build`` workflow. Produces a onefile executable named ``opencut-pyside``
(plus ``.exe`` on Windows) with the FFmpeg/FFprobe binaries, the compiled
translation files and the Qt plugins bundled alongside.

Notes:

* Building on Linux produces a static single-file binary; the companion
  ``build_linux.sh`` script wraps it into an AppImage.
* Building on Windows produces ``opencut-pyside.exe`` — wrap it in an
  installer with Inno Setup / WiX in a follow-up milestone.
* macOS builds are a follow-up (see ROADMAP §5): the spec file is already
  ``sys.platform``-aware so the same file can be reused locally.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# The .spec file is executed from `packaging/` as the current working dir,
# so resolve repo paths relative to this file's directory.
SPEC_DIR = Path(os.path.abspath(SPEC))  # noqa: F821 - PyInstaller-provided
REPO_ROOT = SPEC_DIR.parent.parent if SPEC_DIR.is_file() else Path.cwd()

# Entry point and bundled datas ---------------------------------------

entry_script = str(REPO_ROOT / "main.py")

datas: list[tuple[str, str]] = []

# Ship any compiled translation binaries (.qm). The .ts sources are dev
# artefacts and intentionally omitted.
i18n_dir = REPO_ROOT / "i18n"
if i18n_dir.is_dir():
    for qm in i18n_dir.glob("*.qm"):
        datas.append((str(qm), "i18n"))

# Ship FFmpeg binaries if present under ./bin/.
bin_dir = REPO_ROOT / "bin"
if bin_dir.is_dir():
    suffix = ".exe" if sys.platform == "win32" else ""
    for name in ("ffmpeg", "ffprobe"):
        candidate = bin_dir / f"{name}{suffix}"
        if candidate.is_file():
            datas.append((str(candidate), "bin"))

# Hidden imports: Qt multimedia plugins pulled in only via runtime lookup.
hiddenimports = collect_submodules("PySide6.QtMultimedia")

# PyInstaller analysis --------------------------------------------------

a = Analysis(  # noqa: F821 - PyInstaller-provided
    [entry_script],
    pathex=[str(REPO_ROOT.parent)],  # make 'import app.*' resolvable.
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="opencut-pyside",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
