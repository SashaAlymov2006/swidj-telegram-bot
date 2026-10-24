"""Telegram display dimensions from the actual file, without cropping or stretching."""
import json
import math
from fractions import Fraction
from operations import run_process

def display_metadata(stream, duration=None):
    width, height = int(stream.get("width") or 0), int(stream.get("height") or 0)
    if width <= 0 or height <= 0:
        raise ValueError("Missing video dimensions")
    try:
        sar = Fraction(stream.get("sample_aspect_ratio", "1:1").replace(":", "/"))
        if sar <= 0:
            sar = Fraction(1)
    except (ValueError, ZeroDivisionError, AttributeError):
        sar = Fraction(1)
    width = max(1, round(width * sar))
    rotation = stream.get("tags", {}).get("rotate", 0)
    for side in stream.get("side_data_list", []):
        if "rotation" in side:
            rotation = side["rotation"]
    if round(float(rotation)) % 180 == 90:
        width, height = height, width
    result = {"width": width, "height": height}
    try:
        seconds = float(duration or stream.get("duration") or 0)
        if math.isfinite(seconds) and seconds > 0:
            result["duration"] = math.ceil(seconds)
    except (ValueError, TypeError):
        pass
    return result

def probe_video(path):
    result = run_process(["ffprobe", "-v", "error", "-select_streams", "v:0",
                          "-show_streams", "-show_format", "-of", "json", str(path)],
                         check=True, timeout=30)
    data = json.loads(result.stdout)
    return display_metadata(data["streams"][0], data.get("format", {}).get("duration"))
