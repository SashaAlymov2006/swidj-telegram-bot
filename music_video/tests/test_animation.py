import json,tempfile,unittest
from pathlib import Path
import numpy as np
from music_video.model import validate,movement,PRESETS
from music_video.render import analyse,Scene,render
from music_video.tests.test_pipeline import audio_bytes

class AnimationTests(unittest.TestCase):
    def test_old_defaults_keep_the_original_pulse_and_position(self):
        s=validate({});cx,cy,radius,angle=movement(s,2,[.4,.2,.1,.3,.6],1280,720)
        self.assertEqual((cx,cy),(640,324))
        self.assertAlmostEqual(radius,720*.19*(1+(.4*.13+.6*.03)))
        self.assertAlmostEqual(angle,.14)
        for bad in ({'pulseMode':'invalid'},{'motion':'invalid'},{'lyricsBackdrop':'invalid'},
                    {'animationSpeed':0},{'lyricsOpacity':1},{'motionAmount':True}):
            with self.assertRaises(ValueError):validate(bad)

    def test_text_without_panel_has_no_dark_rectangle_and_speed_does_not_retime_it(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'audio.input').write_bytes(audio_bytes(2));analyse(root)
            (root/'lyrics.json').write_text(json.dumps({'lines':[{'at':0,'text':'First'},{'at':.7,'text':'Second'},{'at':1.4,'text':''},{'at':1.7,'text':'Third'}]}))
            base=dict(shape='none',spectrum='none',particles='none',glow=0,resolution=720,lyricsOn=True,lyricsBackdrop='none')
            feature=np.zeros(53);plain=Scene(root,validate(dict(base,lyricsOn=False))).frame(.8,feature)
            no_panel=Scene(root,validate(base)).frame(.8,feature)
            dark=Scene(root,validate(dict(base,lyricsBackdrop='panel'))).frame(.8,feature)
            point=(102,540)
            self.assertEqual(plain.getpixel(point),no_panel.getpixel(point))
            self.assertLess(sum(dark.getpixel(point)),sum(no_panel.getpixel(point)))
            transparent=Scene(root,validate(dict(base,lyricsBackdrop='panel',lyricsOpacity=0))).frame(.8,feature)
            self.assertEqual(transparent.tobytes(),no_panel.tobytes())
            for speed in (.2,2):
                frame=Scene(root,validate(dict(base,animationSpeed=speed))).frame(.8,feature)
                self.assertEqual(frame.tobytes(),no_panel.tobytes())

    def test_new_templates_export_real_video_with_new_shapes_and_waves(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'audio.input').write_bytes(audio_bytes(.5));analyse(root)
            for name in ('club','festival'):
                scene=validate(dict(PRESETS[name],preset=name,end=.2,resolution=720))
                (root/'scene.json').write_text(json.dumps(scene));render(root)
                self.assertGreater((root/'result.mp4').stat().st_size,1000)
