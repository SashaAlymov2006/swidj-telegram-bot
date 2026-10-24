"""Run SwiDJ through Docker from any PyCharm Python interpreter."""
from pathlib import Path
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
COMPOSE = ROOT / "compose.local.yaml"


def docker_cli():
    found = shutil.which("docker")
    if found:
        return found
    for folder in (Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/DockerDesktop/resources/bin",
                   Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Docker/Docker/resources/bin"):
        candidate = folder / "docker.exe"
        if candidate.is_file():
            os.environ["PATH"] = str(folder) + os.pathsep + os.environ.get("PATH", "")
            return str(candidate)
    raise RuntimeError("Docker Desktop не установлен.")


def engine_ready(cli):
    try:
        result = subprocess.run([cli, "info", "--format", "{{.OSType}}"],
                                capture_output=True, text=True, timeout=8)
        return result.returncode == 0 and result.stdout.strip() == "linux"
    except subprocess.TimeoutExpired:
        return False


def start_engine(cli):
    if engine_ready(cli):
        return
    app = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/DockerDesktop/Docker Desktop.exe"
    if not app.is_file():
        app = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Docker/Docker/Docker Desktop.exe"
    if not app.is_file():
        raise RuntimeError("Откройте Docker Desktop с Linux-контейнерами.")
    startup = None
    if os.name == "nt":
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
    subprocess.Popen([str(app)], startupinfo=startup)
    print("Запускается Docker Desktop…", flush=True)
    for _ in range(36):
        if engine_ready(cli):
            return
        time.sleep(2)
    raise RuntimeError("Docker ещё не готов. Дождитесь его запуска и снова нажмите Run.")


def ensure_cache_volume(cli):
    name = "swidj-model-cache"
    result = subprocess.run([cli, "volume", "inspect", name], capture_output=True)
    if result.returncode:
        subprocess.run([cli, "volume", "create", name], capture_output=True, check=True)


def session_backup():
    from backup_local import create_backup, backup_busy
    if backup_busy():
        print("Резервная копия уже создаётся.")
        return True
    try:
        create_backup(leave_stopped=True)
    except Exception as error:
        print("Резервная копия не создана: " + str(error), file=sys.stderr)
        return False
    return True


def token_configured():
    if os.environ.get("TELEGRAM_TOKEN"):
        return True
    env = ROOT / ".env"
    if not env.is_file():
        return False
    for line in env.read_text(encoding="utf-8-sig").splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip() == "TELEGRAM_TOKEN":
            return bool(re.fullmatch(r"\d{6,}:[A-Za-z0-9_-]{20,}", value.strip().strip("'\"")))
    return False


def command(cli, *arguments):
    return [cli, "compose", "--project-name", "swidj-local", "--file", str(COMPOSE), *arguments]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("run", "stop", "check", "prepare", "logs", "backup"), nargs="?", default="run")
    args = parser.parse_args()
    cli = docker_cli()
    start_engine(cli)
    if args.action == "backup":
        from backup_local import create_backup
        create_backup()
        return 0
    if not (ROOT / ".env").exists():
        shutil.copyfile(ROOT / ".env.example", ROOT / ".env")
    if args.action == "stop":
        result = subprocess.call(command(cli, "stop", "--timeout", "45"), cwd=ROOT)
        if result == 0 and not session_backup():
            return 1
        return result
    if args.action == "logs":
        return subprocess.call(command(cli, "logs", "--tail", "80", "--follow", "bot"), cwd=ROOT)
    subprocess.run(command(cli, "config", "--quiet"), cwd=ROOT, check=True)
    if args.action == "check":
        print(json.dumps({"docker_ready": True, "compose_valid": True,
                          "telegram_token_configured": token_configured()}, ensure_ascii=False))
        return 0
    if args.action == "prepare":
        ensure_cache_volume(cli)
        return subprocess.call(command(cli, "build"), cwd=ROOT)
    if not token_configured():
        print("Заполните TELEGRAM_TOKEN в локальном .env и снова нажмите Run.", flush=True)
        if os.name == "nt":
            subprocess.Popen(["notepad.exe", str(ROOT / ".env")])
        return 2
    ensure_cache_volume(cli)
    print("SwiDJ запускается локально. Для остановки используйте конфигурацию Stop SwiDJ.", flush=True)
    try:
        return subprocess.call(command(cli, "up", "--build", "--abort-on-container-exit",
                                       "--exit-code-from", "bot"), cwd=ROOT)
    finally:
        session_backup()


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
