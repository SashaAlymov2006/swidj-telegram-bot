import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from video_presentation import display_metadata, probe_video
from ui_layout import comfortable_keyboard
from telegram import InlineKeyboardButton as Button

class VideoPresentationTests(unittest.TestCase):
    def test_dimensions_and_orientation(self):
        self.assertEqual(display_metadata({"width":1920,"height":1080}), {"width":1920,"height":1080})
        self.assertEqual(display_metadata({"width":1080,"height":1920}), {"width":1080,"height":1920})
        self.assertEqual(display_metadata({"width":720,"height":576,"sample_aspect_ratio":"64:45"}), {"width":1024,"height":576})
        self.assertEqual(display_metadata({"width":1920,"height":1080,"side_data_list":[{"rotation":-90}]}), {"width":1080,"height":1920})
        self.assertEqual(display_metadata({"width":640,"height":640}), {"width":640,"height":640})

    def test_actual_landscape_and_portrait_files(self):
        with tempfile.TemporaryDirectory() as directory:
            for width,height in ((320,180),(180,320),(160,160)):
                path=Path(directory)/f"{width}.mp4"
                subprocess.run(["ffmpeg","-v","error","-f","lavfi","-i",f"color=size={width}x{height}:rate=1","-t","1","-c:v","libx264","-pix_fmt","yuv420p",str(path)],check=True)
                metadata=probe_video(path)
                self.assertEqual((metadata["width"],metadata["height"]),(width,height))
                self.assertEqual(metadata["duration"],1)

    def test_full_width_choices_keep_paging_compact(self):
        markup=comfortable_keyboard([[Button("Accept",callback_data="accept"),Button("Cancel",callback_data="cancel")],
                                     [Button("Back",callback_data="lib:page:0"),Button("Next",callback_data="lib:page:2")]])
        self.assertEqual([len(row) for row in markup.inline_keyboard],[1,1,2])
