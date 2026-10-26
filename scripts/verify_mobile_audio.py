"""Real audio graph, mobile rate pressure, rack changes and source-seek regression."""
import asyncio,json,os
from pathlib import Path
from aiohttp import web
from playwright.async_api import async_playwright

async def main():
    root=Path('/src/miniapp');app=web.Application()
    async def index(_):return web.Response(text='''<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><button id="start">Start</button><audio id="audio" src="/source.mp3"></audio><script type="module">
import {AudioEngine,chain} from '/assets/audio.js';
window.AudioEngine=AudioEngine;window.audioChain=chain;
const audio=document.querySelector('audio');window.engine=new AudioEngine(audio);
document.querySelector('button').onclick=async()=>{await engine.unlock();await audio.play();window.started=true;};
</script>''',content_type='text/html')
    async def asset(request):return web.FileResponse(root/request.match_info['name'])
    async def media(_):return web.FileResponse('/fixture.mp3')
    app.router.add_get('/',index);app.router.add_get('/assets/{name}',asset)
    app.router.add_get('/source.mp3',media);app.router.add_get('/tone.mp3',media)
    runner=web.AppRunner(app);await runner.setup();await web.TCPSite(runner,'127.0.0.1',8765).start()
    try:
        async with async_playwright() as p:
            for kind in (p.chromium,p.webkit):
                browser=await kind.launch()
                for mobile in (False,True):
                    if os.getenv('QA_PROFILE')=='phone' and not mobile:continue
                    page=await browser.new_page(viewport={'width':390 if mobile else 1280,'height':844},is_mobile=mobile,has_touch=mobile)
                    if mobile and kind.name=='chromium':
                        cdp=await page.context.new_cdp_session(page)
                        await cdp.send('Emulation.setCPUThrottlingRate',{'rate':4})
                    errors=[];page.on('pageerror',lambda err:errors.append(str(err)))
                    await page.goto('http://127.0.0.1:8765/');await page.locator('#start').click()
                    await page.wait_for_function('() => window.started&&audio.currentTime>.1')
                    assert await page.evaluate('engine.livePitch===true'),'Realtime pitch module failed to initialize'
                    await page.wait_for_function('() => engine.pitchNode.metrics?.blockCount>=200&&engine.pitchNode.metrics?.outputRms>.001')
                    pressure=await page.evaluate('''async()=>{
 const descriptor=Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype,'playbackRate');let writes=0;
 const initialUnderruns=engine.pitchNode.metrics?.underrunCount||0;
 Object.defineProperty(audio,'playbackRate',{get(){return descriptor.get.call(this)},set(value){writes++;descriptor.set.call(this,value)}});
 engine.setLinked(true);for(let i=0;i<120;i++)engine.setSpeed(2-i/119*1.5);
 await new Promise(r=>setTimeout(r,100));
 const rateWrites=writes;if(Math.abs(audio.playbackRate-.5)>.0001)throw Error('Final slow tempo lost');
 let previous=audio.currentTime,reversed=false,paused=false;writes=0;
 for(let i=0;i<60;i++){engine.setSpeed(1.5-i/59);await new Promise(r=>setTimeout(r,16));if(audio.currentTime+.02<previous)reversed=true;previous=audio.currentTime;paused=paused||audio.paused;}
 await new Promise(r=>setTimeout(r,60));const dragWrites=writes;
 let convolvers=0;const make=engine.context.createConvolver.bind(engine.context);
 engine.context.createConvolver=()=>{convolvers++;return make()};
 engine.setEffects(['reverb']);await new Promise(r=>setTimeout(r,120));const before=convolvers;
 for(let i=0;i<100;i++)engine.setParams({room_s:.2+i/99*2.8});
 await new Promise(r=>setTimeout(r,350));
 const rebuilt=convolvers-before;
 const analyser=engine.context.createAnalyser();engine.nodes.master.connect(analyser);
 await new Promise(r=>setTimeout(r,150));const samples=new Float32Array(analyser.fftSize);analyser.getFloatTimeDomainData(samples);
 const rms=Math.sqrt(samples.reduce((sum,x)=>sum+x*x,0)/samples.length);
 return {mobile:engine.mobile,rateWrites,dragWrites,reversed,paused,rebuilt,rms,underruns:(engine.pitchNode.metrics?.underrunCount||0)-initialUnderruns,finalPaused:audio.paused,error:audio.error?.message,ready:audio.readyState,time:audio.currentTime};
}''')
                    assert pressure['mobile']==mobile,pressure
                    if mobile:assert pressure['rateWrites']<=3,pressure
                    if mobile:assert pressure['dragWrites']<=40,pressure
                    if mobile:assert pressure['underruns']==0,pressure
                    assert not pressure['reversed'] and not pressure['paused'],pressure
                    assert pressure['rebuilt']==1,pressure
                    assert pressure['rms']>.001,pressure
                    transition=await page.evaluate('''async()=>{
 engine.setEffects([]);audio.currentTime=25;await new Promise(r=>setTimeout(r,200));const before=audio.currentTime;
 const changed=await engine.switchSource(location.origin+'/tone.mp3',{position:before,playing:true});
 const result={changed,before,after:audio.currentTime,seeking:audio.seeking,paused:audio.paused};
 const source=audio.src;const pending=engine.switchSource(location.origin+'/source.mp3',{position:40,playing:true});engine.cancelSourceSwitch();
 result.cancelled=await pending===false&&audio.src===source;return result;
}''')
                    assert transition['changed'] and transition['cancelled'],transition
                    assert transition['after']>=transition['before'] and transition['after']<transition['before']+1,transition
                    assert not transition['seeking'] and not transition['paused'],transition
                    pitch=await page.evaluate('''async()=>{
 engine.setLinked(false);engine.setPitch(-12);engine.setSpeed(1.5);engine.flushRate();
 const analyser=engine.context.createAnalyser();analyser.fftSize=8192;engine.nodes.master.connect(analyser);
 const raw=engine.context.createAnalyser();raw.fftSize=8192;engine.source.connect(raw);
 await new Promise(r=>setTimeout(r,700));const spectrum=new Float32Array(analyser.frequencyBinCount);analyser.getFloatFrequencyData(spectrum);
 let peak=1;for(let i=2;i<spectrum.length;i++)if(spectrum[i]>spectrum[peak])peak=i;
 const input=new Float32Array(raw.frequencyBinCount);raw.getFloatFrequencyData(input);let inputPeak=1;for(let i=2;i<input.length;i++)if(input[i]>input[inputPeak])inputPeak=i;
 return {frequency:peak*engine.context.sampleRate/analyser.fftSize,inputFrequency:inputPeak*engine.context.sampleRate/raw.fftSize,rate:audio.playbackRate,live:engine.livePitch,preserve:audio.preservesPitch,source:audio.src.endsWith('/tone.mp3')};
}''')
                    assert pitch['live'] and pitch['source'] and pitch['rate']==1.5,pitch
                    assert 205<pitch['frequency']<235,pitch
                    waveform=await page.evaluate('''async()=>{
 const context=new OfflineAudioContext(1,44100,44100),osc=context.createOscillator(),level=context.createGain();
 osc.frequency.value=440;level.gain.value=.15;osc.connect(level);osc.start();
 const test=new AudioEngine(document.createElement('audio'),{mobile:false});test.context=context;
 test.nodes=audioChain(context,level,context.destination,0);test.nodes.high.disconnect(test.nodes.compressor);test.rebuildLive();
 const pause=context.suspend(.25137),rendering=context.startRendering();await pause;test.setEffects(['equalizer']);await context.resume();
 const samples=(await rendering).getChannelData(0);let jump=0,peak=0;
 for(let i=10000;i<16000;i++){jump=Math.max(jump,Math.abs(samples[i]-samples[i-1]));peak=Math.max(peak,Math.abs(samples[i]));}
 return {jump,peak,finite:samples.every(Number.isFinite)};
}''')
                    assert waveform['finite'] and waveform['jump']<.08 and waveform['peak']>.05,waveform
                    assert not errors,errors
                    print(json.dumps({'browser':kind.name,'mobile':mobile,'native_rate_writes_for_120_events':pressure['rateWrites'],'native_rate_writes_for_60_slow_drag_events':pressure['dragWrites'],'worklet_starved_blocks_during_stress':pressure['underruns'],'slow_drag_without_pause_or_time_reversal':True,'room_rebuilds_for_100_events':pressure['rebuilt'],'audio_after_old_rack_cleanup':True,'source_position_preserved':True,'independent_minus12_at_1_5_speed_hz':round(pitch['frequency'],2),'transition_max_sample_jump':round(waveform['jump'],5)}),flush=True)
                    await page.close()
                await browser.close()
    finally:await runner.cleanup()

asyncio.run(main())
