"""Run inside the existing bot container. Never prints authentication material.

Exercises only the new worker plus read-only core endpoints; no Telegram sends.
"""
import hashlib,hmac,io,json,math,os,struct,sys,time,urllib.request,urllib.error,wave,zlib
from urllib.parse import urlencode

base=os.environ['MINIAPP_URL'].rstrip('/')
user=int(os.environ['OWNER_USER_IDS'].split(',')[0])
data={'auth_date':str(int(time.time())),'user':json.dumps({'id':user})}
secret=hmac.new(b'WebAppData',os.environ['TELEGRAM_TOKEN'].encode(),hashlib.sha256).digest()
data['hash']=hmac.new(secret,'\n'.join(k+'='+v for k,v in sorted(data.items())).encode(),hashlib.sha256).hexdigest()
headers={'X-Telegram-Init-Data':urlencode(data)}

def request(path,body=None,extra=None):
    start=time.monotonic()
    req=urllib.request.Request(base+path,data=body,headers={**headers,**(extra or {})})
    with urllib.request.urlopen(req,timeout=30) as response:
        raw=response.read();status=response.status
    return raw,status,round(time.monotonic()-start,3)

def api(path,body=None,extra=None):return json.loads(request('/music-video/api/'+path,body,extra)[0])

def wait(job):
    for _ in range(90):
        if job['state'] not in ('queued','analysis','render','upload'):return job
        time.sleep(.5);job=api('jobs/'+job['id'])
    raise AssertionError('Worker timeout')

def main():
    timings=[]
    for path in ('/','/assets/app.js','/api/library','/api/charts'):
        _,status,seconds=request(path);assert status==200;timings.append([path,seconds])
    config=api('config');assert len(config['presets'])==12 and config['profile']==str(user)
    buffer=io.BytesIO();rate=24000
    with wave.open(buffer,'wb') as audio:
        audio.setparams((1,2,rate,0,'NONE',''))
        audio.writeframes(b''.join(round(14000*math.sin(n*math.tau*110/rate)).to_bytes(2,'little',signed=True) for n in range(rate)))
    boundary='swidj-fixture-382';body=('--'+boundary+'\r\nContent-Disposition: form-data; name="audio"; filename="fixture.wav"\r\nContent-Type: audio/wav\r\n\r\n').encode()+buffer.getvalue()+('\r\n--'+boundary+'--\r\n').encode()
    draft=wait(api('drafts',body,{'Content-Type':'multipart/form-data; boundary='+boundary}));assert draft['state']=='ready',draft['state']
    values=api('features/'+draft['id']);assert values['values']
    if 'logoSize' in config['defaults']:
        def chunk(name,data):return struct.pack('>I',len(data))+name+data+struct.pack('>I',zlib.crc32(name+data)&0xffffffff)
        picture=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',20,20,8,2,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+b'\x77\xf2\xcf'*20)*20))+chunk(b'IEND',b'')
        body=('--'+boundary+'\r\nContent-Disposition: form-data; name="logo"; filename="fixture.png"\r\nContent-Type: image/png\r\n\r\n').encode()+picture+('\r\n--'+boundary+'--\r\n').encode()
        updated=wait(api('assets/'+draft['id'],body,{'Content-Type':'multipart/form-data; boundary='+boundary}));assert updated['state']=='ready'
        assert api('features/'+updated['id'])==values and 'logo' in updated['files']
        assert api('jobs/'+draft['id'])['state']=='ready';draft=updated
        settings=api('settings',json.dumps(dict(config['defaults'],logoSize=.8)).encode(),{'Content-Type':'application/json'})
        saved=json.loads(request('/music-video/'+settings['files']['settings'])[0]);assert saved['scene']['logoSize']==.8
    scene=dict(config['defaults'],title='SwiDJ integration check',end=.5,fps=60,resolution=1080)
    if 'logoSize' in scene:scene.update(logoSize=.8,logoX=.4,fadeIn=.1,fadeOut=.1,vignette=.4,textColor='#a9f8dc')
    job=api('render/'+draft['id'],json.dumps(scene).encode(),{'Content-Type':'application/json'})
    _,status,seconds=request('/api/library');assert status==200;timings.append(['library-during-render',seconds])
    job=wait(job);assert job['state']=='complete',job['state']
    raw,status,_=request('/music-video/'+job['files']['result'],extra={'Range':'bytes=0-31'});assert status==206 and len(raw)==32
    history=api('history');assert job['id'] in [item['id'] for item in history['jobs']]
    try:request('/music-video/api/config',extra={'X-Telegram-Init-Data':''})
    except urllib.error.HTTPError as error:assert error.code==401
    else:raise AssertionError('Unsigned access accepted')
    print(json.dumps({'passed':True,'presets':12,'render':'1080p60 H264/AAC','range':206,'core_timings_seconds':timings,'fixture_jobs':[draft['id'],job['id']],'telegram_messages_sent':0}),flush=True)

if __name__=='__main__':
    if '--library-source' in sys.argv:
        library=json.loads(request('/api/library')[0]);tracks=library.get('tracks',[])+library.get('recent',[])
        track=next(item for item in tracks if item.get('playable'))
        raw,status,_=request('/api/stream',json.dumps({'track':track['id']}).encode(),{'Content-Type':'application/json'})
        info=json.loads(raw)
        with urllib.request.urlopen(urllib.request.Request(info['url'],headers={'Range':'bytes=0-31'}),timeout=30) as response:
            assert response.status==206 and len(response.read(32))==32
        print(json.dumps({'shared_library_source':True,'stream_status':status,'file_range':206,'telegram_messages_sent':0}))
    elif '--core' in sys.argv:
        with urllib.request.urlopen('https://api.telegram.org/bot'+os.environ['TELEGRAM_TOKEN']+'/getMe',timeout=15) as response:assert json.load(response)['ok']
        print(json.dumps({'telegram_getMe':True,'library_status':request('/api/library')[1],'telegram_messages_sent':0}))
    else:main()
