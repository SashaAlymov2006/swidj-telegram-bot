import math
import os
import tempfile
import unittest
import wave
from array import array
from pathlib import Path
from unittest.mock import patch
from aiohttp.test_utils import TestClient,TestServer
from miniapp_server import create_app
import test_miniapp as fixtures
TOKEN=fixtures.TOKEN
signed=fixtures.signed
from dj_studio import analyse_pcm

def rhythm(bpm=120,offset=.17,seconds=20):
    samples=array('h')
    for i in range(seconds*2000):
        t=i/2000;phase=(t-offset)%(60/bpm)
        value=24000*math.exp(-phase*65)*math.sin(2*math.pi*95*phase) if t>=offset else 0
        samples.append(round(value))
    return samples.tobytes()

class AnalysisTests(unittest.TestCase):
    def test_known_tempos_and_phase_and_silence(self):
        for bpm in (90,120,150):
            result=analyse_pcm(rhythm(bpm),20)
            self.assertAlmostEqual(result['bpm'],bpm,delta=1)
            distance=(result['offset']-.17)%(60/bpm)
            self.assertLess(min(distance,60/bpm-distance),.06)
            self.assertGreater(result['confidence'],.5)
            self.assertLessEqual(len(result['peaks']),1200)
        self.assertEqual(analyse_pcm(bytes(80000),20)['bpm'],0)
        tone=array('h',(round(12000*math.sin(2*math.pi*440*i/2000)) for i in range(40000)))
        self.assertEqual(analyse_pcm(tone.tobytes(),20)['bpm'],0)

class DJApiTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=fixtures.MiniApiTests.asyncSetUp

    async def test_project_ownership_validation_and_recovery_of_track_reference(self):
        payload={'action':'save','name':'My <set>','project':{'cross':37,'decks':{'A':{'track':'1','pitch':-3,'position':9,'bpm':120,'cues':[1,None,8],'url':'secret'},'B':{}}}}
        response=await self.client.post('/api/dj/projects',headers=self.headers,json=payload)
        self.assertEqual(response.status,200)
        item=(await response.json())['projects'][0];identifier=item['id']
        self.assertEqual(item['decks']['A']['track']['id'],'1');self.assertEqual(item['decks']['A']['pitch'],-3)
        self.assertNotIn('secret',str(item));self.assertNotIn('url',item['decks']['A']['track'])
        self.favorites[77]=[]
        self.assertEqual((await self.bridge.find(77,'1'))['title'],self.song['title'])
        self.assertEqual((await self.client.get('/api/dj/projects')).status,401)
        other={'X-Telegram-Init-Data':signed(78)}
        self.assertEqual((await(await self.client.get('/api/dj/projects',headers=other)).json())['projects'],[])
        self.assertEqual((await self.client.post('/api/dj/projects',headers=other,json={'action':'remove','id':identifier})).status,404)
        bad={'action':'save','name':'Bad','project':{'decks':{'A':{'track':'2'}}}}
        self.assertEqual((await self.client.post('/api/dj/projects',headers=self.headers,json=bad)).status,404)
        for value in (True,999,float('nan')):
            bad={'action':'save','name':'Bad','project':{'decks':{'A':{'pitch':value}}}}
            self.assertEqual((await self.client.post('/api/dj/projects',headers=self.headers,json=bad)).status,400)
        self.assertEqual(len(self.store.load_named('dj_projects')[77]),1)
        response=await self.client.post('/api/dj/projects',headers=self.headers,json={'action':'remove','id':identifier})
        self.assertEqual((await response.json())['projects'],[])

    async def test_actual_audio_analysis_cached_and_owner_checked(self):
        source=Path(self.tmp.name)/'kick.wav'
        with wave.open(str(source),'wb') as stream:
            stream.setparams((1,2,2000,0,'NONE','not compressed'));stream.writeframes(rhythm())
        with patch.dict(os.environ,{'DJ_ANALYSIS_DIR':str(Path(self.tmp.name)/'analysis')}):
            await self.client.close()
            self.client=TestClient(TestServer(create_app(token=TOKEN,bridge=self.bridge)))
            await self.client.start_server();self.addAsyncCleanup(self.client.close)
        with patch.object(self.bridge,'audio_path',return_value=source):
            response=await self.client.get('/api/dj/analysis?track=1',headers=self.headers)
            self.assertEqual(response.status,200);first=await response.json()
            self.assertAlmostEqual(first['bpm'],120,delta=1)
            with patch('dj_studio.process',side_effect=AssertionError('Cache miss')):
                second=await(await self.client.get('/api/dj/analysis?track=1',headers=self.headers)).json()
                self.assertEqual(second,first)
            self.assertEqual((await self.client.get('/api/dj/analysis?track=2',headers=self.headers)).status,404)
            self.assertEqual((await self.client.get('/api/dj/analysis?track=1',headers={'X-Telegram-Init-Data':signed(78)})).status,404)
