import asyncio
import math
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
import wave
from unittest.mock import patch, AsyncMock
from studio_tools import audio_info, timestamp, export_audio
from audio_presentation import music_labels, prepare_music, send_music, fetch_cover


class StudioTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "source.wav"
        with wave.open(str(self.source), "wb") as audio:
            audio.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
            audio.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / 16000))) for i in range(64000)))

    def test_trim_and_conversion_produce_expected_duration_and_preserve_source(self):
        original = self.source.read_bytes()
        for format in ("mp3", "wav"):
            target = self.root / ("cut." + format)
            export_audio(self.source, target, start=1, end=2.5, format=format)
            info = audio_info(target)
            self.assertAlmostEqual(info["duration"], 1.5, delta=0.1)
            self.assertEqual(info["sample_rate"], 44100)
            self.assertEqual(info["channels"], 2)
        self.assertEqual(self.source.read_bytes(), original)

    def test_invalid_ranges_and_time_input_do_not_create_outputs(self):
        self.assertEqual(timestamp("1:30"), 90)
        self.assertEqual(timestamp("2,5"), 2.5)
        for value in ("nan", "-2", "1:75", "1:00:00", "a", "2;whoami"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                timestamp(value)
        target = self.root / "invalid.mp3"
        for start, end in ((2, 1), (-1, 2), (0, 10), (0, float("nan"))):
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                export_audio(self.source, target, start=start, end=end)
        self.assertFalse(target.exists())
        with self.assertRaises(ValueError):
            export_audio(self.source, self.source)
        self.assertTrue(self.source.is_file())

    def test_wav_size_guard_prevents_large_export_before_ffmpeg(self):
        with patch("studio_tools.audio_info", return_value={"duration": 1000}), \
             patch("studio_tools.subprocess.run") as run:
            with self.assertRaises(ValueError):
                export_audio(self.source, self.root / "large.wav", format="wav")
            run.assert_not_called()

    def test_cover_and_tags_are_embedded_and_upload_is_formatted(self):
        from mutagen.mp3 import MP3
        target = self.root / "track.mp3"
        export_audio(self.source, target)
        image = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
             "-i", "color=c=blue:s=80x80", "-frames:v", "1", "-f", "image2pipe",
             "-vcodec", "mjpeg", "pipe:1"], capture_output=True, check=True).stdout
        with patch("audio_presentation.fetch_cover", return_value=image):
            title, artist, filename, thumbnail, duration = prepare_music(
                target, " A <song> ", "Artist", "https://i.ytimg.com/cover.jpg")
        self.assertEqual((title, artist), ("A <song>", "Artist"))
        self.assertNotIn("<", filename)
        tags = MP3(target).tags
        self.assertEqual(str(tags["TIT2"]), "A <song>")
        self.assertEqual(str(tags["TPE1"]), "Artist")
        self.assertTrue(tags.getall("APIC"))
        self.assertTrue(thumbnail)
        bot = type("Bot", (), {"send_audio": AsyncMock()})()
        asyncio.run(send_music(bot, 77, target, title, artist))
        kwargs = bot.send_audio.await_args.kwargs
        self.assertIn("&lt;song&gt;", kwargs["caption"])
        self.assertTrue(kwargs["audio"].filename.endswith(".mp3"))
        self.assertIn("thumbnail", kwargs)

    def test_cover_fetch_rejects_untrusted_urls_without_requests(self):
        with patch("audio_presentation.requests.get") as get:
            for url in ("http://i.ytimg.com/a", "https://127.0.0.1/a", "https://i.ytimg.com.evil.test/a", "https://i.ytimg.com:444/a"):
                self.assertIsNone(fetch_cover(url))
            get.assert_not_called()

    def test_labels_remove_controls_and_filename_separators(self):
        title, artist, filename = music_labels("Title\n / test", "Artist: X")
        self.assertNotIn("\n", title)
        for char in ("/", ":", "\\"):
            self.assertNotIn(char, filename)
        self.assertLessEqual(len(filename), 154)
