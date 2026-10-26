"""Exercise real frontend refresh and lyrics dialogs against isolated API fixtures."""
import asyncio,json
from pathlib import Path
from aiohttp import web
from playwright.async_api import async_playwright

async def main():
    root=Path('/src/miniapp');application=web.Application()
    async def asset(request):
        name=request.match_info.get('name','index.html')
        if name not in ('index.html','app.js','app.css','audio.js','live.js'):raise web.HTTPNotFound()
        return web.FileResponse(root/name)
    application.router.add_get('/',asset);application.router.add_get('/assets/{name}',asset)
    runner=web.AppRunner(application);await runner.setup();await web.TCPSite(runner,'127.0.0.1',8765).start()
    try:
        async with async_playwright() as p:
            for browser_type in (p.chromium,p.webkit):
                browser=await browser_type.launch();page=await browser.new_page(viewport={'width':390,'height':844})
                errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                await page.clock.install()
                await page.add_init_script("window.Telegram={WebApp:{initData:'fixture',initDataUnsafe:{user:{id:77}},ready(){},expand(){}}}")
                await page.route('https://telegram.org/**',lambda route:route.fulfill(body=''))
                calls=[]
                async def api(route):
                    path=route.request.url.split('/api/')[1]
                    if path.startswith('library'):data={'tracks':[{'id':'1','title':'Fixture song','artist':'Artist','source':'Fixture'}],'recent':[],'favorites':['1'],'playlists':[],'language':'en','bot':''}
                    elif path.startswith('charts?'):
                        calls.append(path);data={'source':'Apple Music','country':'de','updated':'2026-10-26T00:00:00Z','source_url':'https://music.apple.com/de/browse/top-charts/songs','tracks':[{'id':'101','rank':1,'title':'Chart '+str(len(calls)),'artist':'Artist','artwork':''}],'stale':False}
                    elif path.startswith('lyrics?'):data={'matches':[{'title':'Fixture song','artist':'Artist','text':'Fixture words','source':'LRCLIB'}]}
                    else:data={}
                    await route.fulfill(json=data)
                await page.route('**/api/**',api)
                await page.goto('http://127.0.0.1:8765/#charts')
                await page.locator('.chart-song strong').wait_for();assert len(calls)==1
                await page.clock.fast_forward(31*60*1000)
                await page.wait_for_function("document.querySelector('.chart-song strong')?.textContent==='Chart 2'")
                assert len(calls)==2
                await page.locator('#mobile-nav [data-go=library]').click()
                await page.locator('.track-row [data-action=menu]').first.click()
                await page.locator('[data-action=lyrics]').click()
                await page.locator('.lyrics-text').wait_for()
                assert await page.locator('.lyrics-text').inner_text()=='Fixture words'
                assert not errors,errors
                print(json.dumps({'browser':browser_type.name,'chart_auto_refresh':True,'lyrics_dialog':True,'js_errors':errors}),flush=True)
                await browser.close()
    finally:await runner.cleanup()

asyncio.run(main())
