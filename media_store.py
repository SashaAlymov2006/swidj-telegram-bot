"""Durable, isolated active audio. Old files are pruned only after state commits."""
import os
from pathlib import Path
import shutil
import tempfile


class MediaStore:
    def __init__(self, root):
        self.root = Path(root)

    def user_directory(self, user_id):
        if type(user_id) is not int or user_id <= 0:
            raise ValueError('A verified numeric Telegram user ID is required')
        if self.root.is_symlink():
            raise ValueError('Audio storage root cannot be a symlink')
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        directory = self.root / str(user_id)
        if directory.is_symlink():
            raise ValueError('User audio directory cannot be a symlink')
        directory.mkdir(mode=0o700, exist_ok=True)
        return directory

    def retain(self, user_id, source):
        directory = self.user_directory(user_id)
        source = Path(source)
        if source.is_symlink() or not source.is_file() or source.stat().st_size == 0:
            raise ValueError('Cannot retain an empty or missing audio source')
        # The temporary and final files share a filesystem, so promotion is atomic.
        pending = None
        try:
            with tempfile.NamedTemporaryFile(dir=directory, suffix='.pending', delete=False) as output:
                pending = Path(output.name)
                with source.open('rb') as input_file:
                    shutil.copyfileobj(input_file, output)
                output.flush()
                os.fsync(output.fileno())
            final = pending.with_suffix('.mp3')
            os.replace(pending, final)
            return str(final)
        except BaseException:
            if pending is not None:
                pending.unlink(missing_ok=True)
            raise

    def prune(self, user_id, keep):
        directory = self.user_directory(user_id)
        keep = Path(keep)
        if keep.is_symlink() or keep.resolve().parent != directory.resolve() or not keep.is_file():
            # A legacy path or a missing source is not permission to delete anything.
            return 0
        removed = 0
        for candidate in directory.iterdir():
            if candidate.is_symlink() or not candidate.is_file() or candidate == keep:
                continue
            if candidate.suffix not in ('.mp3', '.pending'):
                continue
            candidate.unlink(missing_ok=True)
            removed += 1
        return removed


    def trim_cache(self, *, protected_users=(), max_bytes=256 * 1024 * 1024, max_age=24 * 3600):
        """Bound disposable working audio; library files use a separate store."""
        import time
        if self.root.is_symlink() or not self.root.is_dir():
            return 0
        protected = {str(uid) for uid in protected_users}
        files = []
        for directory in self.root.iterdir():
            if directory.is_symlink() or not directory.is_dir() or not directory.name.isdigit():
                continue
            for path in directory.iterdir():
                if path.is_symlink() or not path.is_file() or path.suffix not in (".mp3", ".pending"):
                    continue
                stat = path.stat()
                files.append((stat.st_mtime, stat.st_size, path, directory.name in protected))
        total = sum(item[1] for item in files)
        removed = 0
        now = time.time()
        for modified, size, path, keep in sorted(files, key=lambda item: item[0]):
            if keep:
                continue
            if now - modified > max_age or total > max_bytes:
                path.unlink(missing_ok=True)
                total -= size
                removed += 1
        return removed
