"""Real audio-thread beat-loop capture, release and pause in both browser engines."""
import asyncio,json
from pathlib import Path
from aiohttp import web
from playwright.async_api import async_playwright

async def main():
 app=web.Application()
 async def root(_):return web.Response(text='<html></html>',content_type='text/html')
 async def asset(_):return web.FileResponse('/src/miniapp/dj-loop-processor.js')
 app.router.add_get('/',root);app.router.add_get('/loop.js',asset)
 runner=web.AppRunner(app);await runner.setup();await web.TCPSite(runner,'127.0.0.1',8765).start()
 try:
  async with async_playwright() as p:
   for kind in (p.chromium,p.webkit):
    browser=await kind.launch();page=await browser.new_page();await page.goto('http://127.0.0.1:8765/')
    await page.locator('body').click(position={'x':1,'y':1})
    result=await page.evaluate('''async()=>{
const c=new AudioContext();await c.resume();await c.audioWorklet.addModule('/loop.js');
const loop=new AudioWorkletNode(c,'swidj-roll',{outputChannelCount:[2]}),osc=c.createOscillator(),analyser=c.createAnalyser(),mute=c.createGain();
analyser.fftSize=4096;mute.gain.value=0;osc.connect(loop).connect(analyser).connect(mute).connect(c.destination);
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const frequency=()=>{const bins=new Float32Array(analyser.frequencyBinCount);analyser.getFloatFrequencyData(bins);let at=1;for(let i=2;i<bins.length;i++)if(bins[i]>bins[at])at=i;return at*c.sampleRate/analyser.fftSize;};
const now=c.currentTime;osc.frequency.setValueAtTime(200,now);osc.frequency.linearRampToValueAtTime(1000,now+8);osc.start();loop.port.postMessage({type:'transport',playing:true,feeding:true});
await sleep(2000);const active=new Promise(resolve=>{loop.port.onmessage=({data})=>{if(data.active&&data.loop)resolve();}});
loop.port.postMessage({type:'loop',seconds:.5,delay:.1});await active;await sleep(1400);const held=frequency();
loop.port.postMessage({type:'loop',seconds:0});await sleep(300);const released=frequency();
loop.port.postMessage({type:'transport',playing:false,feeding:false});await sleep(250);const samples=new Float32Array(analyser.fftSize);analyser.getFloatTimeDomainData(samples);const paused=Math.max(...samples.map(Math.abs));
osc.stop();await c.close();return {held,released,paused};}''')
    assert 390<result['held']<485 and result['released']>550 and result['paused']<.00001,result
    print(json.dumps({'browser':kind.name,'quantized_forward_loop_audio':result}),flush=True)
    await browser.close()
 finally:await runner.cleanup()
asyncio.run(main())
