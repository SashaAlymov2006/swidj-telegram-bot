import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
import wave
from unittest.mock import AsyncMock, patch

from aiohttp import FormData
from aiohttp.test_utils import TestClient, TestServer
from miniapp_server import BotLibrary, create_app
from miniapp_studio import plan, render
from state_store import StateStore
from tests.test_miniapp import signed, TOKEN


def audio_bytes(seconds=4):
    stream=io.BytesIO()
    with wave.open(stream,'wb') as audio:
        audio.setparams((1,2,16000,0,'NONE','not compressed'))
        audio.writeframes(b'\x01\x00'*int(16000*seconds))
    return stream.getvalue()


def form(data=None,settings=None,voice=False):
    body=FormData()
    if not voice: body.add_field('settings',json.dumps(settings or {'format':'mp3'}))
    body.add_field('file',data or audio_bytes(),filename='voice.wav' if voice else 'song.wav',content_type='audio/wav')
    return body


class StudioPlanTests(unittest.TestCase):
    def test_bounded_settings_reject_commands_and_nonfinite_numbers(self):
        for settings in [{'format':'http://bad'},{'effect':'echo;exec'}, {'bass':'9;ls'}, {'speed':0}, {'start':8,'end':2}, {'pitch':float('nan')},{'end':999}, {'fade':True}]:
            with self.subTest(settings=settings),self.assertRaises(ValueError):plan(settings,300)
        output=plan({'format':'mp3','speed':.75,'pitch':3,'effect':'reverb','fade':2},300)
        self.assertEqual(output[3],400)
        self.assertIn('afade=t=out',output[4])
        with self.assertRaises(OverflowError):plan({'format':'wav'},1800)


class AppStudioTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store=StateStore(Path(self.tmp.name)/'state.db')
        application=SimpleNamespace(user_data={77:{},78:{}},bot_data={},bot=SimpleNamespace(username='test',send_message=AsyncMock()))
        self.bridge=BotLibrary(application,self.store,{}, {},frozenset(),cache_root=Path(self.tmp.name)/'cache')
        self.client=TestClient(TestServer(create_app(token=TOKEN,bridge=self.bridge)))
        await self.client.start_server()
        self.addAsyncCleanup(self.client.close)
        self.headers={'X-Telegram-Init-Data':signed()}

    async def test_export_mp3_full_five_minutes_without_chat_or_library_writes(self):
        response=await self.client.post('/api/studio',headers=self.headers,data=form(audio_bytes(305),{'format':'mp3','bass':3,'treble':2,'pitch':1,'effect':'echo'}))
        self.assertEqual(response.status,200)
        self.assertEqual(response.content_type,'audio/mpeg')
        target=Path(self.tmp.name)/'five-minutes.mp3'
        target.write_bytes(await response.read())
        from miniapp_studio import probe
        self.assertAlmostEqual(await probe(target),305,delta=.3)
        self.assertEqual(self.bridge.favorites,{})
        self.assertEqual(self.bridge.application.user_data[77],{})
        self.bridge.application.bot.send_message.assert_not_called()

    async def test_multiple_effects_are_combined_and_change_the_actual_sound(self):
        import math,struct
        buffer=io.BytesIO()
        with wave.open(buffer,'wb') as audio:
            audio.setparams((1,2,16000,0,'NONE','not compressed'))
            audio.writeframes(b''.join(struct.pack('<h',int(7000*math.sin(2*math.pi*440*i/16000)+5000*math.sin(2*math.pi*6000*i/16000))) for i in range(32000)))
        outputs=[]
        for effects in [[],['reverb','lofi','compressor']]:
            response=await self.client.post('/api/studio',headers=self.headers,data=form(buffer.getvalue(),{'format':'wav','effects':effects}))
            self.assertEqual(response.status,200)
            with wave.open(io.BytesIO(await response.read())) as audio:
                import numpy as np
                data=np.frombuffer(audio.readframes(audio.getnframes()),dtype='<i2')[::2].astype(float)
                spectrum=abs(np.fft.rfft(data[:44100]))
                outputs.append(spectrum[6000]/max(spectrum[440],1))
        self.assertLess(outputs[1],outputs[0]*.1)
        for effects in [['echo']*9,['private-expression'],{'echo':True}]:
            response=await self.client.post('/api/studio',headers=self.headers,data=form(settings={'effects':effects}))
            self.assertEqual(response.status,400)

    async def test_every_effect_and_an_eight_effect_chain_render(self):
        from miniapp_studio import EFFECTS,probe
        chains=[[key] for key in EFFECTS if key!='none']
        chains.append(['reverb','echo','delay','lofi','normalize','compressor','equalizer','mastering'])
        for effects in chains:
            with self.subTest(effects=effects):
                response=await self.client.post('/api/studio',headers=self.headers,data=form(settings={'format':'wav','effects':effects}))
                self.assertEqual(response.status,200)
                with wave.open(io.BytesIO(await response.read())) as audio:
                    self.assertGreater(audio.getnframes(),1000)

    async def test_wav_trim_preserves_requested_duration(self):
        response=await self.client.post('/api/studio',headers=self.headers,data=form(settings={'format':'wav','start':1,'end':3,'speed':.8,'fade':.4,'effect':'lofi'}))
        self.assertEqual(response.status,200)
        with wave.open(io.BytesIO(await response.read())) as audio:
            self.assertAlmostEqual(audio.getnframes()/audio.getframerate(),2.5,delta=.1)

    async def test_studio_and_voice_auth_controls_invalid_and_capacity(self):
        for endpoint in ['/api/studio','/api/voice']:
            self.assertEqual((await self.client.post(endpoint,data=form())).status,401)
        self.assertEqual((await self.client.post('/api/studio',headers=self.headers,data=form(data=b'not media'))).status,400)
        self.assertEqual((await self.client.post('/api/studio',headers=self.headers,data=form(settings={'pitch':'file:///private'}))).status,400)
        studio=self.client.server.app['studio_bridge']
        self.assertIs(studio,self.bridge)
        controls=SimpleNamespace(settings={'blocked':[77],'maintenance':False},enabled=lambda _:True)
        self.bridge.application.bot_data['controls']=controls
        self.assertEqual((await self.client.post('/api/voice',headers=self.headers,data=form(voice=True))).status,403)

    async def test_voice_returns_editable_words_without_searching_or_messaging(self):
        async def fake_process(args,timeout=240):
            if args[0]=='ffprobe':return json.dumps({'streams':[{}],'format':{'duration':4,'format_name':'wav'}}).encode()
            if args[0]=='ffmpeg':Path(args[-1]).write_bytes(audio_bytes());return b''
            return b'{"text":"Never gonna give you up"}'
        with patch('miniapp_studio.process',side_effect=fake_process):
            response=await self.client.post('/api/voice',headers=self.headers,data=form(voice=True))
        self.assertEqual(response.status,200)
        self.assertEqual((await response.json())['text'],'Never gonna give you up')
        self.assertEqual(self.bridge.searches,{})
        self.bridge.application.bot.send_message.assert_not_called()

    async def test_voice_rejects_long_recording_before_loading_model(self):
        response=await self.client.post('/api/voice',headers=self.headers,data=form(audio_bytes(31),voice=True))
        self.assertEqual(response.status,400)
