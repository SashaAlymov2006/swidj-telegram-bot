"""Check first sound before full transfer and simulated phone keyboard geometry."""
import asyncio,json
from pathlib import Path
from aiohttp import web
from playwright.async_api import async_playwright

async def main():
    root=Path('/src/miniapp');app=web.Application();finished={};active_browser=''
    data=Path('/fixture.mp3').read_bytes()
    async def asset(request):
        if 'name' not in request.match_info:
            html=(root/'index.html').read_text().replace('<script src="https://telegram.org/js/telegram-web-app.js" defer></script>','')
            return web.Response(text=html,content_type='text/html')
        return web.FileResponse(root/request.match_info.get('name','index.html'))
    track={'id':'1','title':'Streaming fixture','artist':'Artist','duration':24}
    async def api(request):
        path=request.match_info['name']
        if path=='library':result={'tracks':[track],'favorites':[],'playlists':[],'language':'en'}
        elif path=='prepare':result={'status':'ready','track':track}
        elif path=='stream':result={'url':'http://127.0.0.1:8765/fixture.mp3?browser='+active_browser}
        else:raise web.HTTPNotFound()
        return web.json_response(result)
    async def stream(request):
        key=request.query.get('browser','')
        bounds=request.http_range
        start=bounds.start or 0;stop=min(bounds.stop or len(data),len(data));body=data[start:stop]
        headers={'Content-Type':'audio/mpeg','Content-Length':str(len(body)),'Accept-Ranges':'bytes'}
        if request.headers.get('Range'):headers['Content-Range']=f'bytes {start}-{stop-1}/{len(data)}'
        if len(body)<=131072:return web.Response(body=body,status=206 if 'Content-Range' in headers else 200,headers=headers)
        finished[key]=False
        response=web.StreamResponse(status=206 if 'Content-Range' in headers else 200,headers=headers)
        await response.prepare(request);await response.write(body[:131072])
        await asyncio.sleep(5)
        try:await response.write(body[131072:]);finished[key]=True
        except ConnectionResetError:pass
        return response
    app.router.add_get('/',asset);app.router.add_get('/assets/{name}',asset);app.router.add_get('/fixture.mp3',stream)
    app.router.add_route('*','/api/{name}',api)
    runner=web.AppRunner(app);await runner.setup();await web.TCPSite(runner,'127.0.0.1',8765).start()
    try:
        async with async_playwright() as p:
            for kind in (p.chromium,p.webkit):
                active_browser=kind.name
                browser=await kind.launch();page=await browser.new_page(viewport={'width':390,'height':844})
                errors=[];page.on('pageerror',lambda err:errors.append(str(err)))
                await page.add_init_script("window.Telegram={WebApp:{initData:'fixture',ready(){},expand(){}}}")
                await page.goto('http://127.0.0.1:8765/')
                await page.locator('.music-card [data-action=play]').first.click()
                try:await page.wait_for_function("document.querySelector('#audio').currentTime>.15",timeout=4000)
                except Exception:
                    print(await page.evaluate("({src:document.querySelector('#audio').src,paused:document.querySelector('#audio').paused,ready:document.querySelector('#audio').readyState,error:document.querySelector('#audio').error?.message,toast:document.querySelector('#toast').textContent})"),flush=True)
                    raise
                assert not finished.get(kind.name), 'Player waited for the whole file'
                await page.locator('#mobile-nav [data-go=search]').click()
                field=page.locator('#search-input');await field.fill('Typed text remains visible')
                assert await field.evaluate('(el)=>parseFloat(getComputedStyle(el).fontSize)')>=16
                await page.evaluate("Object.defineProperty(visualViewport,'height',{configurable:true,get:()=>400});visualViewport.dispatchEvent(new Event('resize'))")
                await page.wait_for_function("document.body.classList.contains('keyboard-open')")
                bounds=await field.bounding_box();assert bounds['y']+bounds['height']<=400
                assert await field.input_value()=='Typed text remains visible'
                await field.blur()
                await page.wait_for_function("!document.body.classList.contains('keyboard-open')")
                assert not errors,errors
                print(json.dumps({'browser':kind.name,'play_before_full_transfer':True,'keyboard_geometry':True,'font_at_least_16px':True}),flush=True)
                await browser.close()
    finally:await runner.cleanup()

asyncio.run(main())
