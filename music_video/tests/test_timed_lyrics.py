import io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import AsyncMock,patch
import numpy as np
from aiohttp import FormData
from music_video.lyrics import parse_lrc,source_metadata,recording,mapped,TimedLyrics
from music_video.model import validate
from music_video.render import analyse,Scene,render
from music_video.tests import test_pipeline as harness
audio_bytes=harness.audio_bytes

SOURCE={'title':'Fixture Song','artist':'Fixture Artist','duration':2}
LRC='[00:00.00]Первая строка\n[00:00.70]Second line\n[00:01.40]\n[00:01.70]Ultima riga'
RECORD={'id':123,'trackName':'Fixture Song','artistName':'Fixture Artist','duration':2,'syncedLyrics':LRC}

class TimingTests(unittest.TestCase):
    def test_multilingual_timing_empty_markers_and_conservative_matching(self):
        lines=parse_lrc(LRC,2);self.assertEqual(lines[1]['at'],.7);self.assertEqual(lines[2]['text'],'')
        self.assertTrue(recording(RECORD,SOURCE))
        for changes in ({'artistName':'Other'},{'duration':8},{'syncedLyrics':None},{'instrumental':True},{'syncedLyrics':'[offset:100]\n'+LRC}):self.assertIsNone(recording(dict(RECORD,**changes),SOURCE))
        self.assertEqual(parse_lrc('[00:01]one line',2),[])
    def test_metadata_and_speed_trim_mapping(self):
        source=source_metadata(dict(SOURCE,start=.5,end=2,speed=2));result=mapped(recording(RECORD,SOURCE),source)
        self.assertEqual(result['lines'][0]['at'],-.25);self.assertEqual(result['lines'][1]['at'],.1)
        self.assertEqual(source_metadata({'disabled':True}),{'disabled':True})
        for change in ({'speed':False},{'start':10},{'duration':float('nan')}):self.assertIsNone(source_metadata(dict(SOURCE,**change)))
    def test_lyrics_frame_changes_at_line_boundaries_and_disappears_during_gap(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'audio.input').write_bytes(audio_bytes(2));analyse(root)
            (root/'lyrics.json').write_text(json.dumps(recording(RECORD,SOURCE)),encoding='utf-8')
            base={'resolution':720,'shape':'none','spectrum':'none','particles':'none','glow':0}
            scene=Scene(root,validate(dict(base,lyricsOn=True)));plain=Scene(root,validate(base));features=np.zeros(53)
            self.assertNotEqual(scene.frame(.1,features).tobytes(),scene.frame(.8,features).tobytes())
            self.assertEqual(scene.frame(1.5,features).tobytes(),plain.frame(1.5,features).tobytes())
            settings=validate(dict(base,lyricsOn=True,lyricsStyle='pulse',end=.2));(root/'scene.json').write_text(json.dumps(settings));render(root)
            self.assertGreater((root/'result.mp4').stat().st_size,1000)

class LyricsApiTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=harness.ApiTests.asyncSetUp
    asyncTearDown=harness.ApiTests.asyncTearDown
    wait=harness.ApiTests.wait
    async def test_conditional_lookup_and_render_snapshot(self):
        form=FormData();form.add_field('audio',audio_bytes(2),filename='fixture.wav');form.add_field('lyric_source',json.dumps(SOURCE))
        draft=await self.wait(await(await self.client.post('/api/drafts',headers=self.headers,data=form)).json(),('queued','analysis'))
        result=await self.client.post('/api/render/'+draft['id'],headers=self.headers,json={'lyricsOn':True,'end':.2});self.assertEqual(result.status,400)
        with patch.object(TimedLyrics,'lookup',new=AsyncMock(return_value=recording(RECORD,SOURCE))) as lookup:
            response=await self.client.post('/api/lyrics/'+draft['id'],headers=self.headers);data=await response.json();self.assertTrue(data['available']);self.assertEqual(len(data['lines']),4);lookup.assert_awaited_once()
        result=await self.client.post('/api/render/'+draft['id'],headers=self.headers,json={'lyricsOn':True,'end':.2,'resolution':720})
        job=await self.wait(await result.json(),('queued','render'));self.assertEqual(job['state'],'complete')
        self.app['jobs'].items[draft['id']]['uid']=2
        self.assertEqual((await self.client.post('/api/lyrics/'+draft['id'],headers=self.headers)).status,404)
    async def test_unknown_or_disabled_recording_has_no_lyrics_button_data(self):
        for source in (None,{'disabled':True},dict(SOURCE,duration=100)):
            form=FormData();form.add_field('audio',audio_bytes(.3),filename='fixture.wav')
            if source:form.add_field('lyric_source',json.dumps(source))
            draft=await self.wait(await(await self.client.post('/api/drafts',headers=self.headers,data=form)).json(),('queued','analysis'))
            with patch.object(TimedLyrics,'lookup',new=AsyncMock()) as lookup:
                response=await self.client.post('/api/lyrics/'+draft['id'],headers=self.headers);self.assertEqual(await response.json(),{'available':False});lookup.assert_not_awaited()
