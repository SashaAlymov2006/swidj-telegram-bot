"""Portable SwiDJ backup: source + persistent runtime data, no API credentials."""
import argparse
from contextlib import contextmanager
import time
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent
EXCLUDED = {".git", ".idea", ".venv", "__pycache__", ".railway", "data", "tmp", ".pytest_cache",
            "downloads", "media", "cache", "node_modules"}
EXTENSIONS = {".py", ".md", ".txt", ".yaml", ".yml", ".ps1", ".xml", ".patch", ".toml",
              ".json", ".png", ".jpg", ".jpeg", ".svg", ".cmd"}
SPECIAL = {"Dockerfile", ".gitignore", ".dockerignore", ".env.example"}
DATA_VOLUME = "swidj-local-data"
IMAGE = "swidj:local-pycharm"


def source_files(root):
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if not path.is_file() or path.is_symlink() or any(part in EXCLUDED for part in relative.parts):
            continue
        if path.name.startswith(".env") and path.name != ".env.example":
            continue
        if any(word in path.name.lower() for word in ("credentials", "service-account", "id_rsa", "cookies")):
            continue
        if path.suffix.lower() in EXTENSIONS or path.name in SPECIAL:
            yield path, relative


def private_values(root):
    values, owners = [], []
    env = root / ".env"
    if env.is_file():
        for line in env.read_text(encoding="utf-8-sig").splitlines():
            key, sep, value = line.partition("=")
            if not sep or line.lstrip().startswith("#"):
                continue
            value = value.strip().strip(chr(34)).strip(chr(39))
            if key.strip() == "OWNER_USER_IDS":
                owners = [int(item) for item in value.split(",") if item.strip().isdecimal()]
            if any(word in key.upper() for word in ("TOKEN", "SECRET", "API_KEY")) and len(value) > 15:
                values.append(value.encode())
    return values, owners


def digest_stream(stream):
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def file_digest(path):
    with open(path, "rb") as stream:
        return digest_stream(stream)


def docker_command(cli, *arguments, check=True):
    result = subprocess.run([cli, *arguments], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and result.returncode:
        raise RuntimeError("Docker не смог выполнить резервное копирование. Работающий бот будет восстановлен.")
    return result


def _create_backup(destination=None, *, leave_stopped=False, source_only=False):
    from run_local import docker_cli, engine_ready, command
    destination = Path(destination) if destination else Path.home() / "Downloads" / "SwiDJ-backups"
    destination = destination.expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    target = destination / ("SwiDJ-" + stamp + ".zip")
    cli, running, runtime = None, False, False
    if not source_only:
        cli = docker_cli()
        if not engine_ready(cli):
            raise RuntimeError("Открой Docker Desktop для копирования данных. Только код: python backup_local.py --source-only")
        state = docker_command(cli, "inspect", "--format", "{{.State.Running}}", "swidj-local-bot-1", check=False)
        running = state.returncode == 0 and state.stdout.strip() == "true"
        volume = docker_command(cli, "volume", "inspect", DATA_VOLUME, check=False)
        if volume.returncode:
            raise RuntimeError("Том данных бота не найден. Для копии только кода используй --source-only.")
    secrets, owners = private_values(ROOT)
    with tempfile.TemporaryDirectory(prefix="swidj-backup-", dir=destination) as temporary:
        work = Path(temporary).resolve()
        assert work.parent == destination
        try:
            if running:
                subprocess.run(command(cli, "stop", "--timeout", "45"), capture_output=True, check=True)
            data = work / "runtime-data.tar.gz"
            if cli:
                export = """import tarfile
from pathlib import Path
with tarfile.open('/out/runtime-data.tar.gz','w:gz') as archive:
    for child in sorted(Path('/data').iterdir()):
        archive.add(child,arcname=child.name)
"""
                docker_command(cli, "run", "--rm", "--network", "none", "--user", "0",
                               "--mount", "type=volume,source=" + DATA_VOLUME + ",target=/data,readonly",
                               "--mount", "type=bind,source=" + str(work) + ",target=/out",
                               "--entrypoint", "python", IMAGE, "-c", export)
                if not data.is_file() or data.stat().st_size == 0:
                    raise RuntimeError("Файл данных не создан.")
                runtime = True
            manifest = {"project": "SwiDJ", "backup_version": 1, "created_utc": stamp,
                        "runtime_included": runtime, "credentials_included": False,
                        "owner_user_ids": owners, "files": {},
                        "runtime_sha256": file_digest(data) if runtime else None}
            pending = work / "bundle.zip"
            with zipfile.ZipFile(pending, "w", zipfile.ZIP_DEFLATED) as archive:
                for path, relative in source_files(ROOT):
                    content = path.read_bytes()
                    if any(secret in content for secret in secrets):
                        raise RuntimeError("Обнаружен секрет в исходниках. Непроверенный архив не сохранён.")
                    # Run configs should use the new laptop's project interpreter.
                    if relative.parts[0] == ".run" and path.suffix == ".xml":
                        text = content.decode("utf-8")
                        text = re.sub(r'<option name="SDK_HOME" value="[^"]*" />',
                                      '<option name="SDK_HOME" value="" />', text)
                        content = text.encode("utf-8")
                    name = "project/" + relative.as_posix()
                    archive.writestr(name, content)
                    manifest["files"][name] = hashlib.sha256(content).hexdigest()
                if runtime:
                    archive.write(data, "recovery/runtime-data.tar.gz", compress_type=zipfile.ZIP_STORED)
                archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
                guide = ROOT / "RESTORE_ON_NEW_LAPTOP.md"
                if guide.is_file():
                    archive.writestr("START_HERE.md", guide.read_bytes())
            with zipfile.ZipFile(pending) as archive:
                if archive.testzip() is not None:
                    raise RuntimeError("Проверка ZIP не прошла.")
                for name, digest in manifest["files"].items():
                    if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                        raise RuntimeError("Контрольная сумма исходников не совпала.")
                if runtime:
                    with archive.open("recovery/runtime-data.tar.gz") as stream:
                        if digest_stream(stream) != manifest["runtime_sha256"]:
                            raise RuntimeError("Контрольная сумма данных не совпала.")
            os.replace(pending, target)
            latest_temp = work / "latest.zip"
            shutil.copyfile(target, latest_temp)
            os.replace(latest_temp, destination / "SwiDJ-latest.zip")
        finally:
            if running and not leave_stopped:
                result = subprocess.run(command(cli, "up", "-d", "--no-build"), capture_output=True)
                if result.returncode:
                    raise RuntimeError("Копия сохранена, но бот не запустился снова. Нажми Run SwiDJ.")
    print(json.dumps({"backup": str(target), "latest": str(destination / "SwiDJ-latest.zip"),
                      "source_files": len(manifest["files"]), "runtime_included": runtime,
                      "credentials_included": False}, ensure_ascii=False))
    return target


@contextmanager
def backup_lock(destination, wait=180):
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    with open(destination / ".backup.lock", "a+b") as lock:
        if lock.tell() == 0:
            lock.write(b"0")
            lock.flush()
        deadline = time.monotonic() + wait
        while True:
            try:
                lock.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Другая копия ещё создаётся.")
                time.sleep(0.2)
        try:
            yield
        finally:
            lock.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def backup_busy(destination=None):
    destination = destination or Path.home() / "Downloads" / "SwiDJ-backups"
    try:
        with backup_lock(destination, wait=0):
            return False
    except TimeoutError:
        return True


def create_backup(destination=None, *, leave_stopped=False, source_only=False):
    destination = destination or Path.home() / "Downloads" / "SwiDJ-backups"
    with backup_lock(destination):
        return _create_backup(destination, leave_stopped=leave_stopped, source_only=source_only)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination")
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()
    create_backup(args.destination, source_only=args.source_only)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error))
