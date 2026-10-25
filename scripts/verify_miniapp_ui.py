"""Exercise our local demo in an isolated browser; never opens user accounts."""
import asyncio
import base64
import json
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import urlopen

from playwright.async_api import async_playwright


async def run():
    output = Path('/out')
    output.mkdir(exist_ok=True)
    errors = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required','--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream'])
        context = await browser.new_context(viewport={'width':1440,'height':1050}, reduced_motion='reduce', accept_downloads=True)
        await context.route('https://telegram.org/**', lambda route: route.fulfill(status=200,body=''))
        page = await context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        await page.goto('http://127.0.0.1:8765')
        await page.locator('.music-card').first.wait_for()
        assert await page.locator('.music-card').count() == 4
        await page.screenshot(path=str(output/'miniapp-desktop.png'),full_page=True)
        assert await page.locator('.mood-card').count()==0
        assert await page.locator('[data-media-mode=video]').count()==1
        await page.locator('.music-card [data-action=play]').first.click()
        await page.locator('#play[aria-label="Пауза"]').wait_for()
        await asyncio.sleep(.2)
        assert await page.evaluate('document.querySelector("audio").currentTime > .1')
        assert await page.locator('#now-title').inner_text() == 'Velvet hours'
        await page.locator('#player-art').click()
        await page.locator('#full-play').wait_for()
        await page.screenshot(path=str(output/'miniapp-now-playing.png'))
        await page.locator('#full-play').click()
        assert await page.evaluate('document.querySelector("audio").paused')
        await page.locator('#full-play').click()
        await page.locator('#dialog .dialog-head button').click()
        # Queue order, removal and persisted resume are independent of chat.
        await page.locator('#desktop-nav [data-go=library]').click()
        await page.locator('.track-row [data-action=menu]').nth(1).click()
        await page.locator('[data-action=queue-next]').click()
        await page.locator('.track-row [data-action=menu]').nth(2).click()
        await page.locator('[data-action=queue-add]').click()
        await page.locator('#open-queue').click()
        assert await page.locator('.queue-row').count()==2
        await page.locator('[data-q-down="0"]').click()
        assert 'After the rain' in await page.locator('.queue-row').first.inner_text()
        await page.locator('[data-q-up="1"]').click()
        assert 'Sunset circuit' in await page.locator('.queue-row').first.inner_text()
        await page.locator('[data-q-remove="1"]').click()
        assert await page.locator('.queue-row').count()==1
        await page.locator('#dialog .dialog-head button').click()
        await page.locator('#next').click()
        await page.wait_for_function("() => document.querySelector('#now-title').textContent==='Sunset circuit'")
        await page.locator('#open-queue').click()
        assert await page.locator('.queue-row').count()==0
        await page.locator('#dialog .dialog-head button').click()
        await page.evaluate('document.querySelector("audio").currentTime=7')
        await page.wait_for_timeout(3300)
        await page.locator('#desktop-nav [data-go=home]').click()
        await page.reload()
        await page.locator('#resume-track').click()
        await page.wait_for_function("() => document.querySelector('#now-title').textContent==='Sunset circuit'")
        assert await page.evaluate('document.querySelector("audio").currentTime>=6')
        await page.locator('#desktop-nav [data-go=studio]').click()
        await page.locator('[data-recipe=warm]').click()
        assert await page.locator('#bass-value').inner_text()=='+3 dB'
        await page.locator('#treble').fill('4')
        await page.locator('#compare-fx').click()
        assert await page.locator('#compare-fx').get_attribute('aria-pressed')=='true'
        await page.locator('#compare-fx').click()
        await page.locator('[data-bass="6"]').click()
        await page.locator('#speed').fill('1.1')
        await page.locator('#preview-mix').click()
        await page.get_by_role('status').filter(has_text='Пример готов').wait_for()
        assert await page.locator('#bass-value').inner_text() == '+6 dB'
        async with page.expect_download() as result:
            await page.locator('#export-mix').click()
        download = await result.value
        await download.save_as(str(output/'browser-export.wav'))
        data = (output/'browser-export.wav').read_bytes()
        assert data[:4] == b'RIFF' and len(data) > 100000
        await page.locator('[data-edit=trimStart]').fill('2')
        await page.locator('[data-edit=trimEnd]').fill('8')
        await page.locator('[data-edit=fade]').fill('1')
        async with page.expect_download() as trimmed:
            await page.locator('#export-mix').click()
        await (await trimmed.value).save_as(str(output/'trimmed-mix.wav'))
        import wave
        with wave.open(str(output/'trimmed-mix.wav')) as wav:
            assert 5.3 < wav.getnframes()/wav.getframerate() < 5.6
        await page.locator('#save-mix').click()
        await page.wait_for_function("() => document.querySelector('#now-title').textContent.includes('SwiDJ mix')")
        assert await page.evaluate('document.querySelector("audio").duration<6')
        await page.locator('#desktop-nav [data-go=library]').click()
        await page.locator('#new-playlist').click()
        await page.locator('#playlist-name').fill('Night drive')
        await page.locator('#dialog [value=create]').click()
        await page.locator('[data-filter=playlists]').click()
        assert 'Night drive' in await page.locator('.playlist-grid').inner_text()
        await page.locator('#language').click()
        assert 'All yours.' in await page.locator('h1').inner_text()
        await page.locator('#desktop-nav [data-go=search]').click()
        await page.locator('#search-input').fill('sunset')
        await page.locator('#search-form .btn').click()
        await page.locator('.track-copy').wait_for()
        assert await page.locator('.track-row').count() == 1
        await page.locator('.track-row [data-action=like]').click()
        await page.locator('#desktop-nav [data-go=library]').click()
        await page.locator('[data-filter=favorites]').click()
        assert 'Sunset circuit' in await page.locator('.track-list').inner_text()
        await page.locator('.track-row').filter(has_text='Sunset circuit').locator('[data-action=menu]').click()
        await page.locator('#dialog [data-action=playlist]').click()
        await page.locator('#dialog [data-add-playlist]').filter(has_text='Night drive').click()
        await page.locator('[data-filter=playlists]').click()
        await page.locator('.playlist-card').filter(has_text='Night drive').click()
        assert 'Sunset circuit' in await page.locator('.track-list').inner_text()
        await page.locator('#playlist-settings').click()
        await page.locator('#rename-playlist').click()
        await page.locator('#playlist-name').fill('Roadtrip')
        await page.locator('#dialog [value=rename]').click()
        assert 'Roadtrip' in await page.locator('.section-head').inner_text()
        await page.locator('.track-row [data-action=menu]').click()
        await page.locator('#dialog [data-action=unlist]').click()
        assert await page.locator('.track-row').count() == 0
        await page.locator('#playlist-settings').click()
        await page.locator('#delete-playlist').click()
        await page.locator('#dialog [value=delete]').click()
        assert 'Roadtrip' not in await page.locator('.playlist-grid').inner_text()
        await page.locator('[data-filter=all]').click()
        assert 'Sunset circuit' in await page.locator('.track-list').inner_text()
        # User titles must remain text, never become markup.
        await page.locator('#new-playlist').click()
        await page.locator('#playlist-name').fill('<img src=x onerror=alert(1)>')
        await page.locator('#dialog [value=create]').click()
        await page.locator('[data-filter=playlists]').click()
        assert await page.locator('.playlist-card img').count() == 0
        # Mobile viewport and navigation/player overlap checks.
        await page.set_viewport_size({'width':390,'height':844})
        await page.locator('#mobile-nav [data-go=home]').click()
        await page.locator('.hero').wait_for()
        await page.locator('.toast.show').wait_for(state='hidden')
        assert await page.locator('.resume-card').count()<=1
        for width in [320,360,390,430,540,720]:
            await page.set_viewport_size({'width':width,'height':844})
            assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            for selector in ['#open-player','#play','#next','#open-queue','#seek']:
                box=await page.locator(selector).bounding_box()
                assert box and box['x']>=0 and box['x']+box['width']<=width+1,(width,selector,box)
            assert (await page.locator('#open-player').bounding_box())['width']>=120
        await page.set_viewport_size({'width':390,'height':844})
        await page.screenshot(path=str(output/'miniapp-mobile.png'))
        assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        player = await page.locator('.player').bounding_box()
        nav = await page.locator('#mobile-nav').bounding_box()
        assert player['y']+player['height'] <= nav['y']+1
        await page.locator('#mobile-nav [data-go=studio]').click()
        await page.locator('.studio-controls').wait_for()
        await page.screenshot(path=str(output/'miniapp-studio-mobile.png'))
        assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        # Exercise the authenticated app UI, not only demo shortcuts. API transport
        # is deterministic here; real signature, ownership and job behavior have
        # separate offline backend tests.
        live = await browser.new_context(viewport={'width':390,'height':844},accept_downloads=True)
        await live.add_init_script("""window.chatOpens=0; window.Telegram={WebApp:{
            initData:'offline-fixture',initDataUnsafe:{user:{first_name:'Fixture',language_code:'en'}},
            ready(){},expand(){},setHeaderColor(){},setBackgroundColor(){},
            openTelegramLink(){window.chatOpens++}
        }};""")
        await live.route('https://telegram.org/**',lambda route:route.fulfill(status=200,body=''))
        tracks=[{'id':str(i),'title':'App recording '+str(i),'artist':'Offline artist','duration':24,
                 'kind':'track','playable':False,'cover':None} for i in (1,2)]
        calls={'send':0,'poll':0,'cancel':False,'track':'1','upload':None}
        audio_fixture=urlopen('http://127.0.0.1:8765/demo/0.wav').read()
        video_fixture=base64.b64decode((Path(__file__).resolve().parent.parent/'tests/fixtures/link_video_base64.txt').read_text())
        async def app_api(route):
            path=route.request.url.split('/api/',1)[-1].split('?',1)[0]
            result={}
            if path=='library':
                if route.request.method=='POST' and route.request.post_data_json.get('action')=='remove':
                    assert route.request.post_data_json['delete_file'] is True
                    calls['upload']=None
                result={'tracks':[calls['upload']] if calls['upload'] else [],'recent':[],
                        'favorites':[calls['upload']['id']] if calls['upload'] else [],'playlists':[],'language':'en','bot':'offline_bot'}
            elif path=='search':result={'tracks':tracks}
            elif path=='prepare':
                calls['track']=route.request.post_data_json['track'];calls['poll']=0;calls['cancel']=False
                result={'job':'a'*24,'status':'queued','track':tracks[int(calls['track'])-1]}
            elif path.endswith('/cancel'):
                calls['cancel']=True;result={'status':'cancelling'}
            elif path.startswith('jobs/'):
                calls['poll']+=1
                status='cancelled' if calls['cancel'] else 'ready' if calls['track']=='1' and calls['poll']>=2 else 'downloading'
                result={'job':'a'*24,'status':status,'track':dict(tracks[int(calls['track'])-1],playable=status=='ready')}
            elif path.startswith('audio/'):
                return await route.fulfill(status=200,body=audio_fixture,content_type='audio/wav')
            elif path=='download':result={'url':'https://preview.example.test/download/'+'a'*32,'filename':'App recording 1.mp3'}
            elif path=='upload':
                assert route.request.headers['content-type'].startswith('multipart/form-data')
                uploaded={'id':'-20000000000000001','title':'My uploaded remix','artist':'','kind':'upload','app_upload':True,'duration':24,'playable':True,'cover':None}
                calls['upload']=uploaded
                result={'track':uploaded,'library':{'tracks':[uploaded],'recent':[],'favorites':[uploaded['id']],'playlists':[],'language':'en','bot':'offline_bot'}}
            elif path=='lyrics':result={'matches':[{'title':'Fixture words','artist':'Fixture artist','text':'Original fixture words\n<img src=x onerror=alert(1)>','source':'LRCLIB'}]}
            elif path=='studio':
                assert route.request.headers['content-type'].startswith(('multipart/form-data','application/json'))
                if route.request.headers['content-type'].startswith('application/json'):calls['studioSettings']=route.request.post_data_json
                if b'"delivery":"ticket"' in route.request.post_data_buffer:
                    return await route.fulfill(status=200,body=json.dumps({'url':'http://127.0.0.1:8765/studio-file/'+'b'*32,'filename':'App recording 1 - SwiDJ mix.mp3','expires_in':600}),content_type='application/json')
                return await route.fulfill(status=200,body=audio_fixture,content_type='audio/mpeg')
            elif path=='link':
                payload=route.request.post_data_json
                mode=payload['mode'];calls['link']=payload
                result={'kind':mode,'title':'Linked fixture','artist':'Fixture','filename':'Linked fixture.'+('mp4' if mode=='video' else 'mp3'),'duration':2,'has_audio':True,'poster':None,'url':'http://127.0.0.1:8765/studio-file/'+('c' if mode=='video' else 'd')*32}
            elif path=='link/audio':result={'kind':'audio','title':'Linked fixture','artist':'Fixture','filename':'Linked fixture.mp3','duration':24,'url':'http://127.0.0.1:8765/studio-file/'+'d'*32}
            elif path=='voice':
                assert route.request.headers['content-type'].startswith('multipart/form-data')
                result={'text':'Never gonna give you up'}
            elif path=='send':calls['send']+=1;result={'ok':True}
            else:raise AssertionError('Unexpected app API path: '+path)
            await route.fulfill(status=200,body=json.dumps(result),content_type='application/json')
        await live.route('**/api/**',app_api)
        async def media_file(route):
            video=route.request.url.endswith('c'*32)
            await route.fulfill(status=200,body=video_fixture if video else audio_fixture,content_type='video/mp4' if video else 'audio/wav')
        await live.route('**/studio-file/**',media_file)
        app_page=await live.new_page()
        app_page.on('pageerror',lambda error:errors.append(str(error)))
        await app_page.goto('http://127.0.0.1:8765/#search')
        await app_page.locator('.voice-panel summary').click()
        await app_page.locator('#record-voice').click()
        await app_page.get_by_role('button',name='Stop recording',exact=True).wait_for()
        await app_page.wait_for_timeout(700)
        await app_page.locator('#record-voice').click()
        await app_page.locator('#transcribe-voice').wait_for()
        await app_page.locator('#transcribe-voice').click()
        await app_page.wait_for_function("() => document.querySelector('#search-input').value==='Never gonna give you up'")
        assert await app_page.locator('.track-row').count()==0
        await app_page.locator('#search-input').fill('recording')
        await app_page.locator('#search-form .btn').click()
        await app_page.locator('.track-row').first.locator('[data-action=play]').first.click()
        await app_page.locator('#activity:not([hidden])').wait_for()
        await app_page.locator('#play[aria-label=Pause]').wait_for()
        assert await app_page.locator('#now-title').inner_text()=='App recording 1'
        await app_page.locator('#mobile-nav [data-go=studio]').click()
        await app_page.locator('#mix-format').select_option('mp3')
        await app_page.locator('[data-effect=reverb]').click()
        await app_page.locator('[data-effect=lofi]').click()
        await app_page.locator('.extra-effects summary').click()
        await app_page.locator('[data-effect=compressor]').click()
        await app_page.wait_for_function("() => document.querySelectorAll('.effect-tile[aria-pressed=true]').length===3")
        assert await app_page.evaluate('!document.querySelector("#audio").paused')
        await app_page.wait_for_function('document.querySelector("#audio").currentTime>0')
        await app_page.locator('#apply-mix').click()
        await app_page.locator('#toast').filter(has_text='Playing your processed mix').wait_for()
        await app_page.locator('#compare-fx').click()
        await app_page.locator('#compare-fx[aria-pressed=true]').wait_for()
        await app_page.locator('#compare-fx').click()
        assert await app_page.evaluate('!document.querySelector("#audio").paused')
        await app_page.locator('#mix-pitch').fill('2')
        await app_page.locator('#mix-pitch').dispatch_event('change')
        await app_page.locator('#toast').filter(has_text='Preview ready').wait_for()
        assert calls['studioSettings']['preview'] is True
        assert calls['studioSettings']['pitch']==2
        assert calls['studioSettings']['linked'] is False
        assert await app_page.evaluate('document.querySelector("#audio").playbackRate===1')
        await app_page.evaluate("window.Telegram.WebApp.downloadFile=(value)=>{window.nativeExport=value};window.Telegram.WebApp.isVersionAtLeast=()=>true")
        await app_page.locator('#export-mix').click()
        await app_page.locator('#native-export').click()
        assert await app_page.evaluate("window.nativeExport.file_name.endsWith('mix.mp3')")
        assert await app_page.evaluate("window.nativeExport.url.includes('/studio-file/')")
        assert await app_page.locator('.export-link').get_attribute('href')==await app_page.evaluate('window.nativeExport.url')
        await app_page.locator('#dialog .dialog-head button').click()
        await app_page.locator('.studio-hero').scroll_into_view_if_needed()
        await app_page.screenshot(path=str(output/'miniapp-expanded-studio.png'),full_page=True)
        await app_page.evaluate('delete window.Telegram.WebApp.downloadFile')
        await app_page.locator('#mobile-nav [data-go=search]').click()
        assert calls['send']==0
        assert await app_page.evaluate('window.chatOpens')==0
        await app_page.locator('.track-row').first.locator('[data-action=menu]').click()
        await app_page.locator('[data-action=lyrics]').click()
        await app_page.locator('.lyrics-text').wait_for()
        assert '<img' in await app_page.locator('.lyrics-text').inner_text()
        assert await app_page.locator('.lyrics-text img').count()==0
        await app_page.locator('#dialog .dialog-head button').click()
        await app_page.locator('.track-row').first.locator('[data-action=menu]').click()
        async with app_page.expect_download() as prepared_download:
            await app_page.locator('#dialog [data-action=download]').click()
        await (await prepared_download.value).save_as(str(output/'app-full-audio.wav'))
        assert (output/'app-full-audio.wav').read_bytes()[:4]==b'RIFF'
        await app_page.evaluate("window.Telegram.WebApp.downloadFile=(value)=>{window.nativeDownload=value};window.Telegram.WebApp.isVersionAtLeast=()=>true")
        await app_page.locator('#player-art').click()
        await app_page.locator('#dialog [data-action=download]').click()
        for _ in range(30):
            if await app_page.evaluate('Boolean(window.nativeDownload)'):
                break
            await asyncio.sleep(.1)
        assert await app_page.evaluate('window.nativeDownload.file_name')=='App recording 1.mp3'
        await app_page.locator('.track-row').nth(1).locator('[data-action=play]').first.click()
        await app_page.locator('#activity:not([hidden])').wait_for()
        await app_page.locator('#cancel-prepare').click()
        await app_page.locator('#activity:not([hidden])').wait_for(state='hidden')
        assert calls['cancel'] and calls['send']==0
        assert await app_page.locator('#now-title').inner_text()=='App recording 1'
        assert await app_page.evaluate('window.chatOpens')==0
        await app_page.screenshot(path=str(output/'miniapp-in-app-playback.png'))
        await app_page.locator('#mobile-nav [data-go=studio]').click()
        await app_page.locator('#local-file').set_input_files(str(output/'app-full-audio.wav'))
        await app_page.locator('#save-local-file').wait_for()
        await app_page.locator('#save-local-file').click()
        await app_page.locator('#save-local-file').wait_for(state='hidden')
        assert await app_page.locator('#now-title').inner_text()=='My uploaded remix'
        await app_page.locator('#mobile-nav [data-go=library]').click()
        await app_page.locator('.track-copy').filter(has_text='My uploaded remix').wait_for()
        artwork=await app_page.locator('.track-row .mini-art').bounding_box()
        title=await app_page.locator('.track-row .track-copy').bounding_box()
        assert artwork['x']+artwork['width'] <= title['x']
        await app_page.screenshot(path=str(output/'miniapp-own-files.png'))
        await app_page.locator('.track-row [data-action=menu]').click()
        await app_page.locator('#dialog [data-action=remove]').click()
        assert 'permanently deleted' in await app_page.locator('#dialog-body').inner_text()
        await app_page.locator('#dialog [value=remove]').click()
        await app_page.locator('.track-row').wait_for(state='hidden')
        assert calls['send']==0 and await app_page.evaluate('window.chatOpens')==0
        await app_page.locator('#mobile-nav [data-go=search]').click()
        await app_page.locator('[data-search-tab=links]').click()
        await app_page.locator('#link-url').fill('https://www.instagram.com/reel/fixture/')
        await app_page.locator('input[name=link-type][value=video]').check()
        assert await app_page.locator('#link-quality option').count()==7
        await app_page.locator('#link-quality').select_option('1080')
        await app_page.locator('#link-quality').select_option('0')
        await app_page.locator('#prepare-link').click()
        await app_page.locator('#link-video').wait_for()
        assert await app_page.locator('#link-video').get_attribute('playsinline') is not None
        assert await app_page.locator('#link-video').get_attribute('controls') is not None
        await app_page.screenshot(path=str(output/'miniapp-video-links.png'))
        assert await app_page.locator('#download-link').inner_text()=='Download video MP4'
        await app_page.locator('#download-link').click()
        assert await app_page.locator('#native-export').inner_text()=='Download video MP4'
        assert await app_page.evaluate('window.nativeDownload.file_name.endsWith(".mp4")')
        await app_page.locator('#dialog .dialog-head button').click()
        await app_page.locator('#extract-link-audio').click()
        await app_page.locator('#download-extracted').wait_for()
        assert await app_page.locator('#link-video').count()==1
        assert await app_page.locator('#download-link').inner_text()=='Download video MP4'
        assert await app_page.locator('#download-extracted').inner_text()=='Download audio MP3'
        await app_page.locator('#download-link').click()
        assert await app_page.evaluate('window.nativeDownload.file_name.endsWith(".mp4")')
        await app_page.locator('#dialog .dialog-head button').click()
        await app_page.locator('#download-extracted').click()
        assert await app_page.evaluate('window.nativeDownload.file_name.endsWith(".mp3")')
        await app_page.locator('#dialog .dialog-head button').click()
        await app_page.locator('#studio-link').click()
        await app_page.locator('[data-speed-preset="1.25"]').click()
        await app_page.locator('[data-tone-preset="0"]').click()
        assert await app_page.locator('#speed').input_value()=='1.25'
        assert await app_page.locator('#mix-pitch').input_value()=='0'
        await app_page.locator('[data-tone-step="-1"]').click()
        assert await app_page.locator('#speed').input_value()=='1.25'
        assert await app_page.locator('#mix-pitch').input_value()=='-1'
        if await app_page.locator('[data-effect=reverb]').get_attribute('aria-pressed')!='true':await app_page.locator('[data-effect=reverb]').click()
        await app_page.locator('#ambience').fill('50')
        assert await app_page.locator('#ambience-value').inner_text()=='50%'
        await app_page.locator('[data-linked=true]').click()
        await app_page.locator('[data-speed-preset="1.5"]').click()
        assert abs(float(await app_page.locator('#mix-pitch').input_value())-7.02)<.1
        assert not await app_page.evaluate('document.querySelector("#audio").preservesPitch')
        await app_page.locator('[data-tone-preset="0"]').click()
        assert float(await app_page.locator('#speed').input_value())==1
        await app_page.locator('[data-linked=false]').click()
        await app_page.locator('[data-speed-preset="1.25"]').click()
        await app_page.locator('[data-tone-preset="2"]').click()
        if not await app_page.locator('.extra-effects').evaluate('(el)=>el.open'):await app_page.locator('.extra-effects summary').click()
        for effect in ['equalizer','stereo','distortion','tremolo']:
            await app_page.locator('[data-effect='+effect+']').click()
        await app_page.locator('.dsp-panel summary').click()
        await app_page.locator('[data-easy-effect=equalizer][data-strength="0"]').click()
        assert await app_page.locator('[data-easy-effect=equalizer][data-strength="0"]').get_attribute('aria-pressed')=='true'
        await app_page.locator('.dsp-panel summary').click()
        assert await app_page.locator('#param-eq60').input_value()=='1'
        await app_page.locator('#param-eq60').fill('6')
        await app_page.locator('#param-comp_ratio').fill('6')
        await app_page.locator('#param-stereo_width').fill('1.5')
        await app_page.locator('#param-drive').fill('3')
        await app_page.locator('#apply-mix').click()
        await app_page.locator('#toast').filter(has_text='Playing your processed mix').wait_for()
        assert calls['studioSettings']['source_ticket']=='d'*32
        assert calls['studioSettings']['params']['eq60']==6
        assert calls['studioSettings']['linked'] is False
        assert abs(calls['studioSettings']['speed']-1.25)<.01
        assert calls['studioSettings']['pitch']==2
        await app_page.locator('.tempo-panel').scroll_into_view_if_needed()
        await app_page.screenshot(path=str(output/'miniapp-remix-controls.png'))
        assert await app_page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        # Verify the live audio graph changes actual samples, not just selected cards.
        ratio=await page.evaluate('''async () => {
          const {connectLive}=await import('/assets/live.js');
          async function measure(effects){
            const ctx=new OfflineAudioContext(1,44100,44100),src=ctx.createBufferSource(),input=ctx.createGain();
            const buffer=ctx.createBuffer(1,44100,44100),samples=buffer.getChannelData(0);
            for(let i=0;i<samples.length;i++)samples[i]=.2*Math.sin(2*Math.PI*440*i/44100)+.2*Math.sin(2*Math.PI*6000*i/44100);
            src.buffer=buffer;src.connect(input);connectLive(ctx,input,ctx.destination,effects);src.start();
            const out=(await ctx.startRendering()).getChannelData(0);
            function power(hz){let a=0,b=0;for(let i=0;i<out.length;i++){a+=out[i]*Math.cos(2*Math.PI*hz*i/44100);b+=out[i]*Math.sin(2*Math.PI*hz*i/44100);}return Math.hypot(a,b);}
            return power(6000)/Math.max(1e-6,power(440));
          }
          return (await measure(['reverb','lofi','compressor']))/(await measure([]));
        }''')
        assert ratio < .2,ratio
        # WebKit exercises the iPhone browser engine without controlling the user's phone.
        safari_browser=await p.webkit.launch()
        safari=await safari_browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
        await safari.add_init_script("window.Telegram={WebApp:{initData:'offline-fixture',initDataUnsafe:{user:{first_name:'Fixture',language_code:'en'}},ready(){},expand(){},setHeaderColor(){},setBackgroundColor(){},isVersionAtLeast(){return true},downloadFile(value){window.nativeFile=value}}};")
        await safari.route('https://telegram.org/**',lambda route:route.fulfill(status=200,body=''))
        await safari.route('**/api/**',app_api)
        await safari.route('**/studio-file/**',media_file)
        iphone=await safari.new_page()
        iphone.on('pageerror',lambda error:errors.append(str(error)))
        await iphone.goto('http://127.0.0.1:8765/#search')
        await iphone.locator('#search-input').fill('recording')
        await iphone.locator('#search-form .btn').click()
        await iphone.locator('.track-row').first.locator('[data-action=play]').first.click()
        await iphone.locator('#now-title').filter(has_text='App recording 1').wait_for()
        if await iphone.evaluate('document.querySelector("#audio").paused'):await iphone.locator('#play').click()
        await iphone.locator('#mobile-nav [data-go=studio]').click()
        await iphone.locator('[data-effect=reverb]').click()
        await iphone.locator('[data-effect=lofi]').click()
        await iphone.locator('#export-mix').click()
        await iphone.locator('#native-export').click()
        assert await iphone.evaluate("window.nativeFile.url.includes('/studio-file/')")
        assert await iphone.evaluate('document.documentElement.scrollWidth<=innerWidth')
        await iphone.screenshot(path=str(output/'miniapp-iphone-download.png'))
        await iphone.locator('#dialog .dialog-head button').click()
        await iphone.locator('#mobile-nav [data-go=search]').click()
        await iphone.locator('[data-search-tab=links]').click()
        await iphone.locator('#link-url').fill('https://www.instagram.com/reel/fixture/')
        await iphone.locator('input[name=link-type][value=video]').check()
        await iphone.locator('#prepare-link').click()
        await iphone.wait_for_function("() => document.querySelector('#link-video')?.videoHeight>0")
        assert await iphone.evaluate('document.querySelector("#link-video").videoHeight>document.querySelector("#link-video").videoWidth')
        assert await iphone.evaluate('document.documentElement.scrollWidth<=innerWidth')
        await iphone.locator('.link-result').scroll_into_view_if_needed()
        await iphone.screenshot(path=str(output/'miniapp-iphone-video.png'))
        await safari_browser.close()
        await browser.close()
    assert not errors, errors
    print(json.dumps({'desktop_mobile_ui':'passed','playback':'passed','studio_preview_wav':'passed',
                      'playlists_search_favorites_languages':'passed','app_prepare_play_download_cancel_without_chat':'passed','browser_errors':errors}))


if __name__ == '__main__':
    server = subprocess.Popen([sys.executable,'miniapp_server.py','--demo'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                urlopen('http://127.0.0.1:8765',timeout=1).close()
                break
            except OSError:
                time.sleep(.1)
        asyncio.run(run())
    finally:
        server.terminate()
        server.wait(timeout=10)
