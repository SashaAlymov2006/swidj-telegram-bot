"""Exercise our local demo in an isolated browser; never opens user accounts."""
import asyncio
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
        browser = await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        context = await browser.new_context(viewport={'width':1440,'height':1050}, reduced_motion='reduce', accept_downloads=True)
        await context.route('https://telegram.org/**', lambda route: route.fulfill(status=200,body=''))
        page = await context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        await page.goto('http://127.0.0.1:8765')
        await page.locator('.music-card').first.wait_for()
        assert await page.locator('.music-card').count() == 4
        await page.screenshot(path=str(output/'miniapp-desktop.png'),full_page=True)
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
            elif path=='send':calls['send']+=1;result={'ok':True}
            else:raise AssertionError('Unexpected app API path: '+path)
            await route.fulfill(status=200,body=json.dumps(result),content_type='application/json')
        await live.route('**/api/**',app_api)
        app_page=await live.new_page()
        app_page.on('pageerror',lambda error:errors.append(str(error)))
        await app_page.goto('http://127.0.0.1:8765/#search')
        await app_page.locator('#search-input').fill('recording')
        await app_page.locator('#search-form .btn').click()
        await app_page.locator('.track-row').first.locator('[data-action=play]').first.click()
        await app_page.locator('#activity:not([hidden])').wait_for()
        await app_page.locator('#play[aria-label=Pause]').wait_for()
        assert await app_page.locator('#now-title').inner_text()=='App recording 1'
        assert calls['send']==0
        assert await app_page.evaluate('window.chatOpens')==0
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
