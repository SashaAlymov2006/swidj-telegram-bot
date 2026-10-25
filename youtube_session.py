"""Give each downloader a disposable private cookie jar, preserving the source."""
from contextlib import contextmanager
from pathlib import Path
import shutil
import tempfile


@contextmanager
def cookie_snapshot(source):
    if not source:
        yield None
        return
    with tempfile.TemporaryDirectory(prefix='swidj-cookie-') as folder:
        copied=Path(folder)/'cookies.txt'
        shutil.copyfile(source,copied)
        copied.chmod(0o600)
        yield str(copied)
