"""Local audio operations with bounded FFmpeg/ffprobe commands."""
import json
import math
from pathlib import Path
import re
import subprocess
from operations import run_process


def audio_info(source):
    try:
        result = run_process(
            ["ffprobe", "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=codec_name,sample_rate,channels:format=duration,size",
             "-of", "json", str(source)], capture_output=True, check=True, timeout=15)
        data = json.loads(result.stdout)
        stream = data["streams"][0]
        duration = float(data["format"]["duration"])
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError()
        return {"duration": duration, "codec": stream.get("codec_name", "?"),
                "sample_rate": int(stream.get("sample_rate", 0)),
                "channels": int(stream.get("channels", 0)),
                "size": Path(source).stat().st_size}
    except (subprocess.SubprocessError, ValueError, KeyError, IndexError, TypeError, OSError) as exc:
        raise ValueError("Не удалось прочитать аудио. Пришли исправный аудиофайл.") from exc


def timestamp(value):
    if not re.fullmatch(r"(?:[0-9]{1,3}:)?[0-9]{1,3}(?:[.,][0-9]{1,3})?", value):
        raise ValueError("Время: секунды или минуты:секунды, например 10 или 0:30.")
    parts = value.replace(",", ".").split(":")
    if len(parts) == 2 and float(parts[1]) >= 60:
        raise ValueError("После двоеточия должно быть меньше 60 секунд.")
    result = float(parts[-1]) + (int(parts[0]) * 60 if len(parts) == 2 else 0)
    return result


def export_audio(source, target, *, start=0, end=None, format="mp3"):
    if format not in ("mp3", "wav", "m4r") or not math.isfinite(start) or start < 0:
        raise ValueError("Некорректные параметры аудио.")
    if Path(source).resolve() == Path(target).resolve():
        raise ValueError("Исходник должен сохраняться отдельно.")
    info = audio_info(source)
    stop = info["duration"] if end is None else end
    if not math.isfinite(stop) or stop <= start or stop > info["duration"] + 0.05:
        raise ValueError("Конец должен быть позже начала и в пределах длительности аудио.")
    duration = min(stop, info["duration"]) - start
    if duration > 1800:
        raise ValueError("Для экспорта выбери фрагмент не длиннее 30 минут.")
    if format == "wav" and duration * 44100 * 2 * 2 > 48 * 1024 * 1024:
        raise ValueError("WAV получится слишком большим. Выбери более короткий фрагмент или MP3.")
    command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
               "-ss", str(start), "-i", str(source), "-t", str(duration),
               "-vn", "-ar", "44100", "-ac", "2"]
    command += (["-c:a", "libmp3lame", "-b:a", "192k"] if format == "mp3" else
                ["-c:a", "aac", "-b:a", "192k", "-f", "ipod"] if format == "m4r" else ["-c:a", "pcm_s16le"])
    try:
        run_process(command + [str(target)], check=True, capture_output=True, timeout=120)
        if not Path(target).is_file() or not 0 < Path(target).stat().st_size <= 49 * 1024 * 1024:
            raise ValueError()
    except (subprocess.SubprocessError, ValueError) as exc:
        Path(target).unlink(missing_ok=True)
        raise ValueError("Не удалось создать файл. Попробуй более короткий фрагмент.") from exc
    return duration
