"""Private scratch files: never clean a checkout, shared /tmp, or another app."""
import os
import shutil
from pathlib import Path
import tempfile
import time

TEMP_ROOT = Path(os.getenv('SWIDJ_TEMP_DIR', Path(tempfile.gettempdir()) / 'swidj'))


def scratch_root():
    if TEMP_ROOT.is_symlink():
        raise ValueError('Scratch directory must not be a symlink')
    TEMP_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    return TEMP_ROOT


def cleanup(path, older_than_sec=600, protected=()):
    root = scratch_root().resolve()
    path = Path(path)
    if path.is_symlink() or path.resolve() != root:
        raise ValueError('Refusing cleanup outside bot scratch directory')
    protected = {Path(p).resolve() for p in protected if p}
    removed = 0
    for child in root.iterdir():
        try:
            # Directories belong to jobs; their owners perform recursive cleanup.
            if child.is_symlink() or not child.is_file() or child.resolve() in protected:
                continue
            if time.time() - child.stat().st_mtime > older_than_sec:
                child.unlink()
                removed += 1
        except FileNotFoundError:
            pass
    return removed


def remove_owned_file(path):
    candidate = Path(path)
    root = scratch_root().resolve()
    if not candidate.is_symlink() and candidate.resolve().is_relative_to(root):
        candidate.unlink(missing_ok=True)
        parent = candidate.parent
        if (not parent.is_symlink() and parent.resolve().parent == root
                and parent.name.startswith(("yt_audio_", "yt_video_", "sc_audio_"))):
            shutil.rmtree(parent, ignore_errors=True)
