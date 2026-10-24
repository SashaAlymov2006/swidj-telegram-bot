"""Bounded, checked FFmpeg processing without shell invocation."""
import subprocess
from operations import run_process
import wave
import array
import math
import sys
from pathlib import Path

FILTERS = {
    'reverb': 'aecho=0.8:0.8:80|140:0.25|0.15',
    'speed_up': 'atempo=1.3', 'slow_down': 'atempo=0.7',
    'normalize': 'loudnorm=I=-16:TP=-1.5:LRA=11',
    'pitch_up': 'aresample=44100,asetrate=52920,aresample=44100,atempo=0.833333',
    'pitch_down': 'aresample=44100,asetrate=35280,aresample=44100,atempo=1.25',
    'lofi': 'aresample=8000,lowpass=f=3000,highpass=f=150,aresample=44100',
    'echo': 'aecho=0.8:0.8:250:0.3', 'delay': 'aecho=0.8:0.8:180|360|540:0.4|0.25|0.15',
    'highpass': 'highpass=f=3000', 'lowpass': 'lowpass=f=300',
    'compressor': 'acompressor=threshold=0.05:ratio=4',
    'equalizer': 'equalizer=f=1000:width_type=o:width=2:g=5',
    'mastering': 'loudnorm=I=-16:TP=-1.5:LRA=11,afftdn',
    'pro_reverb': 'aecho=0.8:0.9:1000:0.3',
}

# Fixed gains keep callback input out of FFmpeg expressions.
BASS_GAINS = {"bass_less": -6, "bass_light": 3, "bass_boost": 6, "bass_strong": 9}
for _name, _gain in BASS_GAINS.items():
    # Headroom before boosting; a limiter catches inter-sample/filter overshoots.
    FILTERS[_name] = (
        f"volume={-max(0, _gain)}dB,bass=g={_gain}:f=100,"
        "alimiter=limit=0.95:level=false:latency=1"
    )


def transcode(source, target, *, audio_filter=None, seconds=None, rate=44100, channels=None):
    command = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
               '-i', str(source), '-vn', '-ar', str(rate)]
    if channels is not None:
        command += ['-ac', str(channels)]
    if seconds is not None:
        command += ['-t', str(seconds)]
    if audio_filter:
        command += ['-af', audio_filter]
    command += [str(target)]
    try:
        run_process(command, check=True, timeout=120, capture_output=True)
        if not Path(target).is_file() or Path(target).stat().st_size == 0:
            raise ValueError('Empty audio output')
    except (subprocess.SubprocessError, ValueError) as exc:
        Path(target).unlink(missing_ok=True)
        raise ValueError('Не удалось обработать аудио: проверьте файл или попробуйте более короткий фрагмент.') from exc


def effect(source, target, name):
    if name not in FILTERS:
        raise ValueError('Неизвестный аудиоэффект')
    transcode(source, target, audio_filter=FILTERS[name])


def recognition_clip(source, target):
    # Short clip bounds processing and request size; never uploads anything.
    transcode(source, target, seconds=12, rate=16000, channels=1)
    with wave.open(str(target)) as audio:
        duration = audio.getnframes() / audio.getframerate()
        samples = array.array('h', audio.readframes(audio.getnframes()))
        if sys.byteorder != 'little':
            samples.byteswap()
        rms = math.sqrt(sum(sample * sample for sample in samples) / max(1, len(samples)))
        if duration < 3:
            raise ValueError('Нужно хотя бы 3 секунды аудио; лучше фрагмент 8–12 секунд с хорошо слышной музыкой.')
    if rms < 10:
        raise ValueError('Запись почти беззвучная. Пришлите фрагмент с хорошо слышной музыкой.')
    return duration
