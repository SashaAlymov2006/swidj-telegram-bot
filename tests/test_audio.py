import math
import struct
import tempfile
import unittest
import wave
from pathlib import Path
from audio_tools import FILTERS, effect, recognition_clip, transcode


class AudioTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'source.wav'
        with wave.open(str(self.source), 'wb') as f:
            f.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
            f.writeframes(b''.join(struct.pack('<h', int(10000 * math.sin(2*math.pi*440*i/16000))) for i in range(64000)))

    def test_all_existing_effects_produce_decodable_audio(self):
        for name in FILTERS:
            with self.subTest(effect=name):
                out = self.root / f'{name}.mp3'
                effect(self.source, out, name)
                decoded = self.root / f'{name}.wav'
                transcode(out, decoded)
                with wave.open(str(decoded)) as f:
                    self.assertGreater(f.getnframes(), 0)

    def test_recognition_format_duration_and_invalid_input(self):
        clip = self.root / 'clip.wav'
        self.assertAlmostEqual(recognition_clip(self.source, clip), 4, places=1)
        with wave.open(str(clip)) as f:
            self.assertEqual((f.getframerate(), f.getnchannels(), f.getsampwidth()), (16000, 1, 2))
        bad = self.root / 'bad.bin';bad.write_bytes(b'not audio')
        with self.assertRaises(ValueError):
            recognition_clip(bad, clip)
        self.assertFalse(clip.exists())

    def test_too_short_and_unknown_effect_rejected(self):
        short = self.root / 'short.wav'
        transcode(self.source, short, seconds=1)
        with self.assertRaises(ValueError):
            recognition_clip(short, self.root / 'clip.wav')
        with self.assertRaises(ValueError):
            effect(self.source, self.root / 'out.mp3', 'invented')

    def test_effects_preserve_stereo_but_recognition_is_mono(self):
        stereo = self.root / 'stereo.wav'
        with wave.open(str(stereo), 'wb') as f:
            f.setparams((2, 2, 16000, 0, 'NONE', 'not compressed'))
            f.writeframes(b''.join(struct.pack('<hh', int(10000 * math.sin(2*math.pi*440*i/16000)),
                int(10000 * math.sin(2*math.pi*660*i/16000))) for i in range(64000)))
        out = self.root / 'stereo-normalized.wav'
        effect(stereo, out, 'normalize')
        with wave.open(str(out)) as f:
            self.assertEqual(f.getnchannels(), 2)
        recognition_clip(stereo, self.root / 'mono.wav')
        with wave.open(str(self.root / 'mono.wav')) as f:
            self.assertEqual(f.getnchannels(), 1)

    def test_silence_does_not_reach_recognition_services(self):
        silent = self.root / 'silence.wav'
        with wave.open(str(silent), 'wb') as f:
            f.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
            f.writeframes(b'\x00\x00' * 64000)
        with self.assertRaisesRegex(ValueError, 'беззвучная'):
            recognition_clip(silent, self.root / 'clip.wav')
