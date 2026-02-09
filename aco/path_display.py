"""Helpers for displaying safe working/storage paths in logs and terminal UI."""

from __future__ import annotations

import os
from pathlib import Path


def _is_same_location(raw_path: str, real_path: Path) -> bool:
    """Return True when raw_path resolves to the same location as real_path."""
    try:
        return Path(raw_path).resolve() == real_path.resolve()
    except Exception:
        return False


def get_display_path(real_workdir: Path) -> str:
    """Return a user-facing path string without forcing symlink resolution."""
    explicit_display = os.getenv("ACO_DISPLAY_PATH")
    if explicit_display:
        return explicit_display

    shell_pwd = os.getenv("PWD")
    if shell_pwd and _is_same_location(shell_pwd, real_workdir):
        return shell_pwd

    # Prefer relative output when we can infer launch cwd; this avoids leaking
    # an absolute resolved path if PWD is unavailable.
    try:
        current_dir = Path.cwd().resolve()
        target_dir = real_workdir.resolve()
        if target_dir == current_dir:
            return "."
        return os.path.relpath(target_dir, start=current_dir)
    except Exception:
        return str(real_workdir)


def get_display_storage_path(real_storage_dir: Path, real_workdir: Path) -> str:
    """Render storage path relative to the display working directory when possible."""
    display_workdir = get_display_path(real_workdir)
    try:
        relative_storage = real_storage_dir.resolve().relative_to(real_workdir.resolve())
    except Exception:
        return get_display_path(real_storage_dir)

    relative_text = relative_storage.as_posix()
    if relative_text in ("", "."):
        return display_workdir
    return f"{display_workdir.rstrip('/')}/{relative_text}"
