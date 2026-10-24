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
        await page.locator('#desktop-nav [data-go=studio]').click()
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
        await browser.close()
    assert not errors, errors
    print(json.dumps({'desktop_mobile_ui':'passed','playback':'passed','studio_preview_wav':'passed',
                      'playlists_search_favorites_languages':'passed','browser_errors':errors}))


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
