"""Full-track automatic pitch, continuous playback and instant tempo regression."""
import asyncio,json
from pathlib import Path
from aiohttp import web
from playwright.async_api import async_playwright

async def main():
    root=Path('/src/miniapp');app=web.Application();calls=[];preferred_language='en'
    track={'id':'1','title':'Full tone fixture','artist':'Artist','duration':60}
    async def asset(request):
        if 'name' not in request.match_info:
            html=(root/'index.html').read_text().replace('<script src="https://telegram.org/js/telegram-web-app.js" defer></script>','')
            return web.Response(text=html,content_type='text/html')
        return web.FileResponse(root/request.match_info['name'])
    async def media(request):return web.FileResponse('/fixture.mp3')
    async def api(request):
        name=request.match_info['name']
        if name=='library':result={'tracks':[track],'favorites':[],'playlists':[],'language':preferred_language}
        elif name=='track/1':result={'track':track}
        elif name=='prepare':result={'status':'ready','track':track}
        elif name=='stream':result={'url':'http://127.0.0.1:8765/source.mp3'}
        elif name=='studio':
            settings=await request.json();calls.append(settings)
            assert settings['preview'] is False and settings['speed']==1
            assert settings['start']==0 and settings['end']==0 and settings['effects']==[]
            assert settings['source_track']=='1'
            await asyncio.sleep(.8)
            result={'url':'http://127.0.0.1:8765/tone.mp3?pitch='+str(settings['pitch']),'expires_in':3600}
        else:raise web.HTTPNotFound()
        return web.json_response(result)
    app.router.add_get('/',asset);app.router.add_get('/assets/{name}',asset)
    app.router.add_get('/source.mp3',media);app.router.add_get('/tone.mp3',media)
    app.router.add_route('*','/api/{name:.*}',api)
    runner=web.AppRunner(app);await runner.setup();await web.TCPSite(runner,'127.0.0.1',8765).start()
    try:
        async with async_playwright() as p:
            for kind in (p.chromium,p.webkit):
                calls.clear();browser=await kind.launch();page=await browser.new_page(viewport={'width':390,'height':844})
                errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
                await page.add_init_script("window.Telegram={WebApp:{initData:'fixture',ready(){},expand(){}}}")
                await page.goto('http://127.0.0.1:8765/')
                await page.locator('.music-card [data-action=play]').first.click()
                await page.wait_for_function("() => document.querySelector('#audio').currentTime>.1")
                await page.locator('#mobile-nav [data-go=studio]').click()
                await page.locator('[data-tone-preset="2"]').click()
                before=await page.locator('#audio').evaluate('(el)=>el.currentTime')
                await page.wait_for_timeout(850)
                assert await page.locator('#audio').evaluate('(el)=>el.currentTime')>before
                await page.wait_for_function("() => document.querySelector('#audio').src.includes('pitch=2')")
                await page.wait_for_function("() => document.querySelector('#audio').duration>59")
                await page.locator('#audio').evaluate('(el)=>el.currentTime=25')
                await page.locator('[data-speed-preset="1.5"]').click()
                source=await page.locator('#audio').get_attribute('src')
                await page.wait_for_timeout(900)
                assert 'pitch=2' in source
                assert await page.locator('#audio').evaluate('(el)=>el.currentTime>25&&!el.paused&&el.playbackRate===1.5')
                assert len(calls)==1,'Changing tempo should not transcode pitch again'
                await page.locator('[data-tone-preset="0"]').click()
                await page.wait_for_function("() => document.querySelector('#audio').src.endsWith('/source.mp3')")
                await page.locator('[data-tone-preset="2"]').click()
                await page.wait_for_function("() => document.querySelector('#audio').src.includes('pitch=2')")
                assert len(calls)==1,'Repeated pitch should use its prepared full track'
                slider=page.locator('#mix-pitch')
                await slider.fill('3');await slider.dispatch_event('change')
                await page.wait_for_timeout(700)
                await slider.fill('4');await slider.dispatch_event('change')
                await page.wait_for_timeout(750)
                assert 'pitch=2' in await page.locator('#audio').get_attribute('src'),'An obsolete render must not replace the playing track'
                await page.wait_for_function("() => document.querySelector('#audio').src.includes('pitch=4')")
                assert await page.locator('#audio').evaluate('(el)=>el.playbackRate===1.5&&!el.paused')
                await page.locator('[data-linked=true]').click()
                await page.wait_for_function("() => document.querySelector('#audio').readyState>=2&&!document.querySelector('#audio').paused")
                count=len(calls)
                await page.evaluate("""async()=>{
                    const audio=document.querySelector('#audio');window.sliderReloads=0;
                    audio.addEventListener('loadstart',()=>window.sliderReloads++);
                    for(const id of ['speed','mix-pitch'])for(let i=0;i<24;i++){
                        const slider=document.getElementById(id);
                        slider.value=id==='speed'?String(.6+i*.05):String(-6+i*.5);
                        slider.dispatchEvent(new Event('input',{bubbles:true}));
                        await new Promise(requestAnimationFrame);
                    }
                }""")
                assert await page.evaluate('window.sliderReloads===0')
                assert await page.locator('#audio').evaluate('(el)=>!el.paused&&!el.preservesPitch')
                assert len(calls)==count,'Linked slider drags must not request server processing'
                preferred_language='ru'
                await page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
                await page.wait_for_function("() => document.documentElement.lang==='ru'")
                preferred_language='en'
                linked=await browser.new_page(viewport={'width':390,'height':844})
                await linked.add_init_script("window.Telegram={WebApp:{initData:'fixture',ready(){},expand(){}}}")
                await linked.goto('http://127.0.0.1:8765/?track=1#studio')
                await linked.locator('#now-title').filter(has_text='Full tone fixture').wait_for()
                assert await linked.locator('.studio-source h2').inner_text()=='Full tone fixture'
                await linked.locator('#play').click()
                await linked.wait_for_function("() => document.querySelector('#audio').currentTime>.1")
                await linked.close()
                assert not errors,errors
                print(json.dumps({'browser':kind.name,'full_track_over_15s':True,'playback_continues_during_processing':True,'instant_speed_without_reprocessing':True,'cached_pitch':True,'obsolete_tone_ignored':True,'linked_slider_drag_no_reload_or_requests':True}),flush=True)
                await browser.close()
    finally:await runner.cleanup()

asyncio.run(main())
