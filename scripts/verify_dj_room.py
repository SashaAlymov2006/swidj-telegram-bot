"""Exercise the actual Mini App presets, shared-context decks, roll and recording."""
import asyncio,json,base64
from pathlib import Path
from aiohttp import web
from playwright.async_api import async_playwright

async def main():
    root=Path('/src/miniapp');app=web.Application();presets=[];studio_calls=[];saved=[]
    tracks=[{'id':str(i),'title':'Deck '+key,'artist':'Fixture','duration':60,'playable':True} for i,key in [(1,'A'),(2,'B')]]
    async def asset(request):
        name=request.match_info.get('name')
        if not name:return web.Response(text=(root/'index.html').read_text().replace('<script src="https://telegram.org/js/telegram-web-app.js" defer></script>',''),content_type='text/html')
        return web.FileResponse(root/name)
    async def media(request):return web.FileResponse('/fixture-b.mp3' if request.match_info.get('id')=='2' else '/fixture.mp3')
    async def api(request):
        nonlocal presets
        name=request.match_info['name']
        if name=='library':result={'tracks':tracks,'favorites':[],'playlists':[],'language':'en'}
        elif name=='prepare':result={'status':'ready','track':tracks[int((await request.json())['track'])-1]}
        elif name=='stream':result={'url':'http://127.0.0.1:8765/source-'+str((await request.json())['track'])+'.mp3'}
        elif name=='presets':
            if request.method=='POST':
                payload=await request.json()
                if payload['action']=='save':presets.append({'id':'abcdef12','name':payload['name'],'settings':payload['settings']})
                elif payload['action']=='remove':presets=[p for p in presets if p['id']!=payload['id']]
            result={'presets':presets}
        elif name=='studio':
            assert request.content_type=='multipart/form-data'
            reader=await request.multipart();part=await reader.next();settings=json.loads(await part.text());part=await reader.next();data=await part.read()
            assert settings['format']=='mp3' and len(data)>1000
            studio_calls.append({'bytes':len(data),'settings':settings,'data':data,'mime':part.headers.get('Content-Type','audio/wav')})
            result={'url':'http://127.0.0.1:8765/studio-file/'+'f'*32,'filename':'SwiDJ DJ set.mp3','expires_in':3600}
        elif name=='studio/save':
            saved.append(await request.json());result={'track':{'id':'-3','title':'SwiDJ DJ set','artist':'SwiDJ','kind':'upload'},'library':{'tracks':tracks,'favorites':[],'playlists':[],'language':'en'}}
        else:raise web.HTTPNotFound()
        return web.json_response(result)
    app.router.add_get('/',asset);app.router.add_get('/assets/{name}',asset);app.router.add_get('/source-{id}.mp3',media);app.router.add_get('/studio-file/{ticket}',media);app.router.add_route('*','/api/{name:.*}',api)
    runner=web.AppRunner(app);await runner.setup();await web.TCPSite(runner,'127.0.0.1',8765).start()
    out=Path('/out');out.mkdir(exist_ok=True)
    try:
        async with async_playwright() as p:
            for kind in (p.chromium,p.webkit):
                presets=[];studio_calls.clear();saved.clear()
                browser=await kind.launch();page=await browser.new_page(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
                errors=[];page.on('pageerror',lambda err:errors.append(str(err)))
                await page.add_init_script('''window.Telegram={WebApp:{initData:'fixture',ready(){},expand(){},isVersionAtLeast(){return true},downloadFile(file){window.qaDownload=file}}};
window.qaAudio=[];const NativeAudio=Audio;window.Audio=function(...args){const value=new NativeAudio(...args);window.qaAudio.push(value);return value};
window.qaContexts=0;const NativeContext=AudioContext;window.AudioContext=function(...args){window.qaContexts++;return new NativeContext(...args)};
if(globalThis.MediaRecorder){const NativeRecorder=MediaRecorder;window.MediaRecorder=function(...args){try{const r=new NativeRecorder(...args);window.qaRecorder=r;return r;}catch(e){window.qaRecorderError={name:e.name,message:e.message};throw e}};window.MediaRecorder.isTypeSupported=NativeRecorder.isTypeSupported.bind(NativeRecorder);}
''')
                await page.goto('http://127.0.0.1:8765/#studio')
                await page.locator('#my-sound-presets summary').click()
                await page.locator('#bass-value').wait_for()
                await page.locator('[data-bass="3"]').click()
                await page.locator('#save-sound-preset').click()
                await page.locator('#sound-preset-name').fill('My <night> sound')
                await page.locator('#dialog-form button[value=save]').click()
                await page.locator('[data-sound-preset]').wait_for()
                assert presets[0]['settings']['bass']==3
                await page.locator('#reset-fx').click();await page.locator('[data-sound-preset]').click()
                assert await page.locator('#bass-value').inner_text()=='+3 dB'
                assert await page.locator('#sound-preset-list night').count()==0
                await page.locator('[data-studio-mode=dj]').click()
                await page.locator('[data-dj-deck=A]').wait_for()
                for key,identifier in [('A','1'),('B','2')]:
                    await page.locator(f'[data-dj-action=load][data-deck={key}]').click()
                    await page.locator(f'[data-dj-pick="{identifier}"]').click()
                    await page.locator(f'[data-dj-title={key}]').filter(has_text='Deck '+key).wait_for()
                await page.locator('[data-dj-action=start-all]').click()
                await page.wait_for_function('() => qaAudio.length===2&&qaAudio.every(a=>!a.paused&&a.currentTime>.2)')
                assert await page.evaluate('qaContexts===1'),'Decks created separate contexts'
                assert await page.evaluate('qaAudio[0].src.includes("source-1")&&qaAudio[1].src.includes("source-2")')
                assert await page.locator('#audio').evaluate('(el)=>el.paused')
                await page.locator('#language').click();await page.wait_for_timeout(100);await page.evaluate('window.scrollTo(0,0)')
                assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                await page.screenshot(path=str(out/('dj-room-initial-'+kind.name+'.png')))
                await page.locator('#language').click()
                await page.locator('#dj-cross').fill('0');await page.wait_for_timeout(400)
                assert await page.locator('[data-dj-deck=A] meter').evaluate('(el)=>el.value>.005')
                assert await page.locator('[data-dj-deck=B] meter').evaluate('(el)=>el.value<.001')
                await page.locator('#dj-cross').fill('100');await page.wait_for_timeout(400)
                assert await page.locator('[data-dj-deck=A] meter').evaluate('(el)=>el.value<.001')
                assert await page.locator('[data-dj-deck=B] meter').evaluate('(el)=>el.value>.005')
                await page.locator('[data-dj-action=center]').click()
                await page.locator('[data-dj-action=cue][data-deck=A][data-cue="0"]').click()
                assert ' · ' in await page.locator('[data-dj-action=cue][data-deck=A][data-cue="0"]').inner_text()
                for key in ['A','B']:await page.locator(f'[data-dj-deck={key}] summary').click()
                await page.locator('[data-dj-control=bpm][data-deck=A]').fill('120')
                await page.locator('[data-dj-control=bpm][data-deck=B]').fill('100')
                await page.locator('[data-dj-action=sync][data-deck=B]').click()
                assert abs(float(await page.locator('[data-dj-control=speed][data-deck=B]').input_value())-1.2)<.01
                await page.wait_for_timeout(2200)
                await page.locator('[data-dj-action=roll][data-deck=A][data-seconds="2"]').click()
                await page.wait_for_timeout(500)
                assert await page.locator('[data-dj-action=roll][data-deck=A][data-seconds="2"]').evaluate('(el)=>el.classList.contains("active")')
                await page.locator('[data-dj-control=pitch][data-deck=A]').fill('-3')
                await page.locator('[data-dj-control=speed][data-deck=A]').fill('0.85')
                await page.wait_for_timeout(300)
                assert await page.evaluate('qaAudio.every(a=>!a.paused)')
                await page.locator('[data-dj-action=record]').click();await page.wait_for_timeout(2200)
                await page.locator('[data-dj-action=record]').click()
                try:await page.locator('.dj-export').wait_for(state='visible',timeout=10000)
                except Exception:
                    print(await page.evaluate("({state:window.qaRecorder?.state,mime:window.qaRecorder?.mimeType,error:window.qaRecorderError,toast:document.querySelector('#toast').textContent,record:document.querySelector('#dj-record-state').textContent,support:['audio/mp4','audio/webm;codecs=opus','audio/webm'].map(t=>[t,globalThis.MediaRecorder?.isTypeSupported(t)])})"),flush=True)
                    raise
                await page.locator('[data-dj-action=download]').click()
                await page.wait_for_function('() => window.qaDownload?.file_name.endsWith(".mp3")')
                data=bytes(studio_calls[-1]['data']);mime=studio_calls[-1]['mime']
                recording=await page.evaluate('''async encoded=>{const data=Uint8Array.from(atob(encoded),c=>c.charCodeAt(0));const buffer=await new OfflineAudioContext(2,1,44100).decodeAudioData(data.buffer);const samples=buffer.getChannelData(0);const amplitude=f=>{const n=Math.min(samples.length,buffer.sampleRate),at=samples.length-n,k=2*Math.cos(2*Math.PI*f/buffer.sampleRate);let a=0,b=0;for(let i=at;i<samples.length;i++){const c=samples[i]+k*a-b;b=a;a=c;}return 2*Math.sqrt(a*a+b*b-k*a*b)/n;};return {duration:buffer.duration,rms:Math.sqrt(samples.reduce((s,n)=>s+n*n,0)/samples.length),deckA:amplitude(370),deckB:amplitude(880)}}''',base64.b64encode(data).decode())
                assert recording['duration']>1.5 and recording['rms']>.002,recording
                assert recording['deckA']>.005 and recording['deckB']>.005,recording
                extension='wav' if 'wav' in mime else 'mp4' if 'mp4' in mime else 'webm'
                (out/('dj-record-'+kind.name+'.'+extension)).write_bytes(data)
                await page.locator('#dialog .dialog-head button').click()
                await page.locator('[data-dj-action=save]').click()
                await page.wait_for_function('() => document.querySelector("#dj-record-state").textContent.includes("ready")')
                assert len(studio_calls)==1 and len(saved)==1
                assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                await page.screenshot(path=str(out/('dj-room-'+kind.name+'.png')),full_page=True)
                await page.locator('[data-studio-mode=sound]').click()
                await page.wait_for_function('() => qaAudio.every(a=>a.paused)')
                await page.locator('[data-studio-mode=dj]').click()
                assert await page.locator('[data-dj-title=A]').inner_text()=='Deck A'
                await page.locator('[data-dj-action=pause-all]').click()
                roll=await page.evaluate("""async()=>{
 const context=new AudioContext();await context.resume();await context.audioWorklet.addModule('/assets/dj-loop-processor.js');
 const node=new AudioWorkletNode(context,'swidj-roll',{outputChannelCount:[2]}),osc=context.createOscillator(),analyser=context.createAnalyser(),silent=context.createGain();
 analyser.fftSize=4096;silent.gain.value=0;osc.connect(node).connect(analyser).connect(silent).connect(context.destination);
 const now=context.currentTime;osc.frequency.setValueAtTime(200,now);osc.frequency.linearRampToValueAtTime(800,now+8);osc.start();node.port.postMessage({type:'transport',playing:true,feeding:true});
 await new Promise(r=>setTimeout(r,2300));
 const active=new Promise(resolve=>{node.port.onmessage=({data})=>{if(data.active)resolve();}});node.port.postMessage({type:'roll',seconds:2});await active;
 await new Promise(r=>setTimeout(r,2600));const spectrum=new Float32Array(analyser.frequencyBinCount);analyser.getFloatFrequencyData(spectrum);let peak=1;for(let i=2;i<spectrum.length;i++)if(spectrum[i]>spectrum[peak])peak=i;
 const frequency=peak*context.sampleRate/analyser.fftSize;node.port.postMessage({type:'transport',playing:false,feeding:false});await new Promise(r=>setTimeout(r,250));
 const samples=new Float32Array(analyser.fftSize);analyser.getFloatTimeDomainData(samples);const pausedPeak=Math.max(...samples.map(Math.abs));osc.stop();await context.close();return {frequency,pausedPeak};
}""")
                assert 190<roll['frequency']<430 and roll['pausedPeak']<.00001,roll
                assert not errors,errors
                print(json.dumps({'browser':kind.name,'mobile':True,'named_presets':True,'shared_audio_context':True,'crossfader':True,'cue_roll_and_tempo_match':True,'recorded_audio_seconds':round(recording['duration'],2),'recorded_audio_rms':round(recording['rms'],4),'single_mp3_export_and_shared_library_save':True,'js_errors':errors}),flush=True)
                await browser.close()
    finally:await runner.cleanup()

asyncio.run(main())
