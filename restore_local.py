"""Restore an extracted SwiDJ bundle; existing data are never overwritten."""
import json
from pathlib import Path
import subprocess
from backup_local import file_digest, DATA_VOLUME, IMAGE
from run_local import docker_cli, start_engine, command, ensure_cache_volume

ROOT = Path(__file__).resolve().parent


def restore():
    bundle = ROOT.parent
    manifest_path = bundle / "manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError("Распакуй весь архив и запусти restore_local.py из папки project.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("project") != "SwiDJ" or manifest.get("backup_version") != 1:
        raise RuntimeError("Это не поддерживаемая копия SwiDJ.")
    for name, expected in manifest["files"].items():
        path = (bundle / name).resolve()
        if not path.is_relative_to(bundle.resolve()) or not path.is_file() or file_digest(path) != expected:
            raise RuntimeError("Проверка исходников не прошла. Распакуй архив ещё раз.")
    data = bundle / "recovery/runtime-data.tar.gz"
    if manifest.get("runtime_included") and (not data.is_file() or file_digest(data) != manifest["runtime_sha256"]):
        raise RuntimeError("Проверка копии данных не прошла.")
    cli = docker_cli()
    start_engine(cli)
    running = subprocess.run([cli, "inspect", "--format", "{{.State.Running}}", "swidj-local-bot-1"],
                             capture_output=True, text=True)
    if running.returncode == 0 and running.stdout.strip() == "true":
        raise RuntimeError("Бот уже запущен на этом компьютере. Восстановление не выполнялось.")
    env_path = ROOT / ".env"
    if not env_path.exists():
        text = (ROOT / ".env.example").read_text(encoding="utf-8")
        owners = ",".join(str(uid) for uid in manifest.get("owner_user_ids", []) if type(uid) is int and uid > 0)
        text = text.replace("OWNER_USER_IDS=\n", "OWNER_USER_IDS=" + owners + "\n")
        env_path.write_text(text, encoding="utf-8")
    print("Собираю зависимости. При первом запуске нужен интернет.", flush=True)
    subprocess.run(command(cli, "build"), cwd=ROOT, check=True)
    ensure_cache_volume(cli)
    if manifest.get("runtime_included"):
        subprocess.run([cli, "volume", "create", DATA_VOLUME], capture_output=True, check=True)
        probe = subprocess.run([cli, "run", "--rm", "--network", "none", "--user", "0",
            "--mount", "type=volume,source=" + DATA_VOLUME + ",target=/data",
            "--entrypoint", "python", IMAGE, "-c",
            "from pathlib import Path; import sys; sys.exit(2 if any(Path('/data').iterdir()) else 0)"], capture_output=True)
        if probe.returncode:
            raise RuntimeError("На компьютере уже есть данные SwiDJ. Ничего не перезаписано.")
        code = """import os,tarfile
from pathlib import Path,PurePosixPath
with tarfile.open('/recovery/runtime-data.tar.gz','r:gz') as archive:
    members=archive.getmembers()
    for member in members:
        path=PurePosixPath(member.name)
        if path.is_absolute() or '..' in path.parts or not (member.isdir() or member.isfile()):
            raise ValueError('Unsupported backup member')
    archive.extractall('/data',members=members,filter='data')
for path in [Path('/data'),*Path('/data').rglob('*')]:
    os.chown(path,10001,10001)
"""
        subprocess.run([cli, "run", "--rm", "--network", "none", "--user", "0",
            "--mount", "type=volume,source=" + DATA_VOLUME + ",target=/data",
            "--mount", "type=bind,source=" + str(data.parent) + ",target=/recovery,readonly",
            "--entrypoint", "python", IMAGE, "-c", code], check=True)
    print("Восстановлено. Добавь TELEGRAM_TOKEN в личный .env, затем: python run_local.py run")


if __name__ == "__main__":
    try:
        restore()
    except (RuntimeError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error))
