import math
import struct
import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from audio_tools import effect, BASS_GAINS
from bass_labels import BASS_LABELS
from studio_ui import handle_studio
from i18n_ui import english


class BassTests(unittest.IsolatedAsyncioTestCase):
    async def test_level_replaces_previous_and_retains_other_effects(self):
        with tempfile.NamedTemporaryFile() as source:
            state = {"last_audio_path": source.name, "pending_effects": ["echo", "bass_strong"],
                     "effect_preview": {"token": "old"}}
            query = SimpleNamespace(answer=AsyncMock(), edit_message_text=AsyncMock())
            update = SimpleNamespace(callback_query=query)
            context = SimpleNamespace(user_data=state)
            await handle_studio(update, context, BASS_LABELS, "studio:bass:bass_light")
            self.assertEqual(state["pending_effects"], ["echo", "bass_light"])
            self.assertNotIn("effect_preview", state)
            await handle_studio(update, context, BASS_LABELS, "studio:bass:off")
            self.assertEqual(state["pending_effects"], ["echo"])
            await handle_studio(update, context, BASS_LABELS, "studio:bass:injected")
            self.assertEqual(state["pending_effects"], ["echo"])
            self.assertEqual(query.edit_message_text.await_count, 2)

    def test_bass_strength_changes_audio_without_clipping_or_shortening(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.wav"
            rate = 44100
            with wave.open(str(source), "wb") as audio:
                audio.setparams((2, 2, rate, 0, "NONE", "not compressed"))
                audio.writeframes(b"".join(struct.pack("<hh", v, v) for v in (
                    int(14000 * math.sin(2*math.pi*70*i/rate) +
                        14000 * math.sin(2*math.pi*1500*i/rate))
                    for i in range(rate*2))))
            ratios = []
            for name in BASS_GAINS:
                target = Path(folder) / (name + ".wav")
                effect(source, target, name)
                with wave.open(str(target)) as audio:
                    self.assertEqual(audio.getnchannels(), 2)
                    self.assertAlmostEqual(audio.getnframes()/audio.getframerate(), 2, delta=.01)
                    samples = struct.unpack("<" + "h"*(audio.getnframes()*2), audio.readframes(audio.getnframes()))[::2]
                self.assertLess(max(abs(v) for v in samples), 32767)
                # Compare bass to midrange after filter startup.
                samples = samples[rate//2:]
                def amplitude(hz):
                    return abs(sum(v * complex(math.cos(2*math.pi*hz*i/rate),
                                               math.sin(2*math.pi*hz*i/rate))
                                   for i,v in enumerate(samples)))
                ratios.append(amplitude(70)/amplitude(1500))
            self.assertEqual(ratios, sorted(ratios))
            self.assertGreater(ratios[-1], ratios[1]*1.3)

    def test_bass_ui_is_translated(self):
        for label in list(BASS_LABELS.values()) + ["Регулировка баса", "Без изменения",
                "Выбери уровень → послушай пример → примени к треку."]:
            self.assertFalse(any("а" <= c.lower() <= "я" for c in english(label)))
