import asyncio
import hashlib
import hmac
import io
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from urllib.parse import urlencode
import wave
import numpy as np
from PIL import Image
from aiohttp import FormData
from aiohttp.test_utils import TestClient,TestServer
from music_video.model import validate,DEFAULTS,PRESETS,dimensions
from music_video.render import analyse,analyse_assets,Scene,render,sample,ffmpeg
from music_video.server import create_app,telegram_user

def audio_bytes(seconds=1.2):
    rate=24000;t=np.arange(round(seconds*rate))/rate
    envelope=np.where((t%.5)<.15,.6,.08)
    pcm=(envelope*np.sin(2*np.pi*90*t)+.06*np.sin(2*np.pi*3000*t))*25000
    buffer=io.BytesIO()
    with wave.open(buffer,'wb') as out:out.setparams((1,2,rate,0,'NONE',''));out.writeframes(pcm.astype('<i2').tobytes())
    return buffer.getvalue()

class ModelTests(unittest.TestCase):
    def test_javascript_fixture_matches_server_schema(self):
        data=json.loads((Path(__file__).parent/'model-config.json').read_text())
        self.assertEqual(data,{'defaults':DEFAULTS,'presets':PRESETS})
    def test_settings_reject_invalid_values_and_preserve_full_track_default(self):
        self.assertEqual(validate({})['end'],0)
        self.assertEqual(dimensions(validate({'aspect':'portrait'})),(1080,1920))
        for value in ({'fps':120},{'fps':True},{'strength':float('nan')},{'title':'bad\ntext'},{'color':'url(https://bad)'},{'unknown':1},{'start':5,'end':4}):
            with self.subTest(value=value),self.assertRaises(ValueError):validate(value)
    def test_auth_is_signed_expiring_and_has_no_duplicate_fields(self):
        token='123:fixture';data={'auth_date':str(int(time.time())),'user':json.dumps({'id':77})}
        secret=hmac.new(b'WebAppData',token.encode(),hashlib.sha256).digest();data['hash']=hmac.new(secret,'\n'.join(k+'='+v for k,v in sorted(data.items())).encode(),hashlib.sha256).hexdigest()
        raw=urlencode(data);self.assertEqual(telegram_user(raw,token),77)
        for bad in (raw+'&user={}',raw.replace('77','78'),raw.replace(data['hash'],'0'*64)):
            with self.assertRaises(ValueError):telegram_user(bad,token)

class RendererTests(unittest.TestCase):
    def test_composition_crop_and_fades_change_frames_without_changing_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);body=audio_bytes(1);(root/'audio.input').write_bytes(body)
            Image.new('RGB',(300,70),'orange').save(root/'background.input',format='PNG');analyse(root)
            values=np.load(root/'features.npy');settings=validate({'resolution':720,'backgroundKind':'image','logoX':.25,'logoSize':.6,'fit':'contain','vignette':.5,'blur':3,'fadeIn':.2,'fadeOut':.2,'textColor':'#ff00aa'})
            scene=Scene(root,settings);first=scene.frame(0,sample(values,0));middle=scene.frame(.5,sample(values,.5))
            self.assertEqual(np.asarray(first).max(),0);self.assertGreater(np.asarray(middle).mean(),1)
            self.assertEqual((root/'audio.input').read_bytes(),body)
            for key in ('logoX','logoSize','vignette','fadeIn'):
                with self.assertRaises(ValueError):validate({key:1000})
    def test_audio_drives_scene_and_all_presets_render_deterministically(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'audio.input').write_bytes(audio_bytes())
            Image.new('RGBA',(150,110),'orange').save(root/'logo.input',format='PNG')
            Image.new('RGB',(180,100),'navy').save(root/'background.input',format='PNG')
            analyse(root);values=np.load(root/'features.npy')
            self.assertEqual(values.shape[1],53);self.assertTrue(np.isfinite(values).all());self.assertGreater(values[:,3].max()-values[:,3].min(),.05)
            for name,preset in PRESETS.items():
                scene=Scene(root,validate(dict(preset,preset=name,resolution=720,backgroundKind='image',title='Тест / Visual')))
                first=scene.frame(.3,sample(values,.3));second=scene.frame(.3,sample(values,.3))
                self.assertEqual(first.tobytes(),second.tobytes());self.assertEqual(first.size,(1280,720))
                self.assertNotEqual(first.tobytes(),scene.frame(.7,sample(values,.7)).tobytes())
    def test_real_mp4_at_both_frame_rates_with_background_video_and_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'audio.input').write_bytes(audio_bytes(.7));analyse(root)
            subprocess.run([ffmpeg(),'-v','error','-f','lavfi','-i','color=c=blue:s=160x100:r=30','-t','0.3','-pix_fmt','yuv420p','-y',str(root/'background.input.mp4')],check=True)
            os.replace(root/'background.input.mp4',root/'background.input')
            analyse_assets(root)
            for fps in (30,60):
                (root/'scene.json').write_text(json.dumps(validate({'fps':fps,'resolution':720,'end':.3,'backgroundKind':'video','particleCount':5,'fadeIn':.1,'fadeOut':.1,'fit':'contain','logoX':.4,'preset':'vinyl','spectrum':'mirror','spinLogo':True})))
                render(root);self.assertGreater((root/'result.mp4').stat().st_size,1000)
                result=subprocess.run([ffmpeg(),'-hide_banner','-i',str(root/'result.mp4'),'-t','0','-f','null','-'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                text=result.stderr.decode(errors='replace');self.assertIn('1280x720',text);self.assertIn(f'{fps} fps',text);self.assertIn('Audio: aac',text)

class ApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_settings_export_is_validated_and_downloadable_without_audio(self):
        result=await self.client.post('/api/settings',headers=self.headers,json={'title':'My style','logoX':.3,'fadeOut':1})
        self.assertEqual(result.status,200);job=await result.json()
        response=await self.client.get('/'+job['files']['settings']);self.assertIn('attachment',response.headers['Content-Disposition'])
        data=await response.json();self.assertEqual(data['type'],'swidj-visual-style');self.assertEqual(data['scene']['logoX'],.3)
        self.assertEqual((await self.client.post('/api/settings',headers=self.headers,json={'logoX':2})).status,400)
    async def test_image_update_reuses_audio_features_and_preserves_previous_draft(self):
        form=FormData();form.add_field('audio',audio_bytes(.3),filename='source.wav')
        image=io.BytesIO();Image.new('RGB',(32,32),'red').save(image,format='PNG');red=image.getvalue()
        form.add_field('logo',red,filename='red.png')
        draft=await self.wait(await(await self.client.post('/api/drafts',headers=self.headers,data=form)).json(),('queued','analysis'))
        self.assertEqual(draft['state'],'ready');old=self.app['jobs'].folder(draft)
        audio_hash=hashlib.sha256((old/'audio.input').read_bytes()).digest();features_hash=hashlib.sha256((old/'features.npy').read_bytes()).digest()
        image=io.BytesIO();Image.new('RGB',(32,32),'blue').save(image,format='PNG');blue=image.getvalue()
        form=FormData();form.add_field('logo',blue,filename='blue.png')
        result=await self.client.post('/api/assets/'+draft['id'],headers=self.headers,data=form)
        self.assertEqual(result.status,200);updated=await self.wait(await result.json(),('queued','analysis'));self.assertEqual(updated['state'],'ready')
        new=self.app['jobs'].folder(updated)
        self.assertEqual(audio_hash,hashlib.sha256((new/'audio.input').read_bytes()).digest());self.assertEqual(features_hash,hashlib.sha256((new/'features.npy').read_bytes()).digest())
        self.assertEqual((old/'logo.input').read_bytes(),red);self.assertEqual((new/'logo.input').read_bytes(),blue)
        self.assertNotEqual((old/'logo.png').read_bytes(),(new/'logo.png').read_bytes());self.assertFalse((new/'audio.f32').exists())
        form=FormData();form.add_field('remove_logo','1',content_type='text/plain')
        removed=await self.wait(await(await self.client.post('/api/assets/'+updated['id'],headers=self.headers,data=form)).json(),('queued','analysis'))
        self.assertEqual(removed['state'],'ready');self.assertNotIn('logo',removed['files']);self.assertTrue((old/'logo.png').exists())
        self.app['jobs'].items[draft['id']]['uid']=2
        form=FormData();form.add_field('remove_logo','1',content_type='text/plain')
        self.assertEqual((await self.client.post('/api/assets/'+draft['id'],headers=self.headers,data=form)).status,404)
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.app=create_app(self.tmp.name,dev=True)
        self.client=TestClient(TestServer(self.app));await self.client.start_server()
        self.headers={'X-SwiDJ-Local':'1'}
    async def asyncTearDown(self):
        await self.client.close()
        for attempt in range(20):
            try:self.tmp.cleanup();break
            except PermissionError:
                if os.name!='nt' or attempt==19:raise
                await asyncio.sleep(.05)
    async def wait(self,job,states):
        for _ in range(150):
            result=await self.client.get('/api/jobs/'+job['id'],headers=self.headers);job=await result.json()
            if job['state'] not in states:return job
            await asyncio.sleep(.1)
        self.fail('Worker timed out')
    async def test_full_upload_preview_render_download_and_owner_isolation(self):
        self.assertEqual((await self.client.get('/api/config')).status,403)
        self.assertEqual((await self.client.get('/api/config',headers={**self.headers,'Origin':'https://external.example'})).status,403)
        form=FormData();form.add_field('audio',audio_bytes(),filename='my.wav',content_type='audio/wav')
        response=await self.client.post('/api/drafts',headers=self.headers,data=form);self.assertEqual(response.status,200)
        draft=await self.wait(await response.json(),('queued','analysis'));self.assertEqual(draft['state'],'ready')
        features=await(await self.client.get('/api/features/'+draft['id'],headers=self.headers)).json();self.assertTrue(features['values'])
        result=await self.client.post('/api/render/'+draft['id'],headers=self.headers,json=validate({'resolution':720,'end':.25,'fps':60,'shape':'triangle','title':'Demo'}))
        job=await self.wait(await result.json(),('queued','render'));self.assertEqual(job['state'],'complete')
        media=await self.client.get('/'+job['files']['result'],headers={'Range':'bytes=0-31'});self.assertEqual(media.status,206);self.assertEqual(len(await media.read()),32)
        self.assertIn('attachment',media.headers['Content-Disposition'])
        self.app['jobs'].items[job['id']]['uid']=2
        self.assertEqual((await self.client.get('/api/jobs/'+job['id'],headers=self.headers)).status,404)
        history=await(await self.client.get('/api/history',headers=self.headers)).json();self.assertFalse(history['jobs'])
        self.assertEqual((await self.client.get('/files/'+job['id']+'/wrong/result')).status,404)
    async def test_cancel_queued_job_does_not_start_it_and_bad_scene_rejected(self):
        jobs=self.app['jobs'];job=jobs.create(1,'draft');job['state']='queued';jobs.save(job)
        response=await self.client.post('/api/cancel/'+job['id'],headers=self.headers);self.assertEqual((await response.json())['state'],'cancelled')
        self.assertEqual((await self.client.post('/api/render/'+job['id'],headers=self.headers,json={'fps':100})).status,409)
    async def test_invalid_audio_fails_without_blocking_next_job(self):
        form=FormData();form.add_field('audio',b'not media',filename='bad.wav',content_type='audio/wav')
        response=await self.client.post('/api/drafts',headers=self.headers,data=form)
        job=await self.wait(await response.json(),('queued','analysis'));self.assertEqual(job['state'],'failed')
        form=FormData();form.add_field('audio',audio_bytes(.2),filename='valid.wav',content_type='audio/wav')
        response=await self.client.post('/api/drafts',headers=self.headers,data=form)
        job=await self.wait(await response.json(),('queued','analysis'));self.assertEqual(job['state'],'ready')
    async def test_active_render_cancel_stops_process_and_preserves_draft(self):
        form=FormData();form.add_field('audio',audio_bytes(5),filename='source.wav',content_type='audio/wav')
        draft=await self.wait(await(await self.client.post('/api/drafts',headers=self.headers,data=form)).json(),('queued','analysis'))
        response=await self.client.post('/api/render/'+draft['id'],headers=self.headers,json=validate({'resolution':1080,'fps':60,'particleCount':100}))
        job=await response.json()
        for _ in range(100):
            status=await(await self.client.get('/api/jobs/'+job['id'],headers=self.headers)).json()
            if status['state']=='render' and self.app['jobs'].process:break
            await asyncio.sleep(.02)
        response=await self.client.post('/api/cancel/'+job['id'],headers=self.headers);self.assertEqual((await response.json())['state'],'cancelled')
        for _ in range(100):
            if self.app['jobs'].active is None:break
            await asyncio.sleep(.02)
        self.assertIsNone(self.app['jobs'].active)
        still=await(await self.client.get('/api/jobs/'+draft['id'],headers=self.headers)).json();self.assertEqual(still['state'],'ready')
    async def test_scene_rejects_nan_and_assets_are_not_overwritten_by_new_scene(self):
        jobs=self.app['jobs'];draft=jobs.create(1,'draft');draft['state']='ready'
        (jobs.folder(draft)/'analysis.json').write_text(json.dumps({'duration':1,'backgroundKind':'color'}))
        scene=validate({'title':'Original'})
        response=await self.client.post('/api/render/'+draft['id'],headers=self.headers,json=dict(scene,glow=float('nan')))
        self.assertEqual(response.status,400)
        self.assertFalse((jobs.folder(draft)/'scene.json').exists())

class LimitsAndRestart(unittest.TestCase):
    def test_restart_marks_running_jobs_interrupted_and_keeps_complete_results(self):
        from music_video.server import Jobs
        with tempfile.TemporaryDirectory() as directory:
            jobs=Jobs(directory);pending=jobs.create(77,'video');pending['state']='render';jobs.save(pending)
            complete=jobs.create(78,'video');complete['state']='complete';jobs.save(complete)
            (jobs.folder(complete)/'result.mp4').write_bytes(b'fixture')
            restored=Jobs(directory)
            self.assertEqual(restored.get(77,pending['id'])['state'],'interrupted')
            self.assertEqual(restored.payload(restored.get(78,complete['id']))['state'],'complete')
            with self.assertRaises(Exception):restored.get(77,complete['id'])
    def test_expired_files_pruned_but_active_draft_kept(self):
        from music_video.server import Jobs
        with tempfile.TemporaryDirectory() as directory:
            jobs=Jobs(directory);old=jobs.create(77,'draft');old['state']='ready';old['expires']=0;jobs.save(old)
            active=jobs.create(77,'draft');active['state']='render';active['expires']=0;jobs.save(active);jobs.active=active['id']
            jobs.prune();self.assertNotIn(old['id'],jobs.items);self.assertIn(active['id'],jobs.items)
