"""Non-destructive production API audit; run inside the bot container.

No send endpoints, library mutations, account passwords or secret output.
"""
import hashlib,hmac,io,json,math,os,sqlite3,subprocess,sys,tempfile,time,urllib.request,urllib.error,wave
from pathlib import Path
from urllib.parse import urlencode
BASE=os.environ['MINIAPP_URL'].rstrip('/')
UIDS=[int(value) for value in os.environ['OWNER_USER_IDS'].split(',')]

def request(path,body=None,content='application/json',uid=None,headers=None):
    data={'auth_date':str(int(time.time())),'user':json.dumps({'id':uid or UIDS[0]})}
    secret=hmac.new(b'WebAppData',os.environ['TELEGRAM_TOKEN'].encode(),hashlib.sha256).digest()
    data['hash']=hmac.new(secret,'\n'.join(k+'='+v for k,v in sorted(data.items())).encode(),hashlib.sha256).hexdigest()
    auth={'X-Telegram-Init-Data':urlencode(data),'Content-Type':content,**(headers or {})}
    if isinstance(body,dict):body=json.dumps(body).encode()
    with urllib.request.urlopen(urllib.request.Request(BASE+path,data=body,headers=auth),timeout=180) as response:return response.read(),response.status,response.headers

def api(path,body=None,**kwargs):return json.loads(request(path,body,**kwargs)[0])
def check(name,run):
    start=time.monotonic()
    try:details=run() or {};print(json.dumps({'check':name,'ok':True,'seconds':round(time.monotonic()-start,2),**details}),flush=True)
    except Exception as error:print(json.dumps({'check':name,'ok':False,'error':type(error).__name__,'status':getattr(error,'code',None),'seconds':round(time.monotonic()-start,2)}),flush=True)
def multipart(audio,settings=None):
    boundary='swidj-audit-file-8472';body=bytearray()
    if settings is not None:body.extend(('--'+boundary+'\r\nContent-Disposition: form-data; name="settings"\r\n\r\n'+json.dumps(settings)+'\r\n').encode())
    body.extend(('--'+boundary+'\r\nContent-Disposition: form-data; name="file"; filename="fixture.wav"\r\nContent-Type: audio/wav\r\n\r\n').encode());body.extend(audio);body.extend(('\r\n--'+boundary+'--\r\n').encode())
    return bytes(body),'multipart/form-data; boundary='+boundary
def fingerprint(library):return {key:library.get(key) for key in ('language','favorites','playlists','tracks')}
def voice_check():
    body,content=multipart(Path('/tmp/swidj-voice-fixture.wav').read_bytes());result=json.loads(request('/api/voice',body,content)[0]);assert result.get('text','').strip();return {'transcript_characters':len(result['text'])}

def main():
    before={uid:fingerprint(api('/api/library',uid=uid)) for uid in UIDS}
    for index,uid in enumerate(UIDS):check('library-language-account-'+str(index),lambda uid=uid:{'language':before[uid].get('language'),'tracks':len(before[uid].get('tracks') or [])})
    def auth():
        try:request('/api/library',headers={'X-Telegram-Init-Data':''})
        except urllib.error.HTTPError as error:assert error.code==401;return {'unsigned':401}
        raise AssertionError('Unsigned access accepted')
    check('authorization',auth)
    results=[]
    def search(query):
        response=api('/api/search?q='+urlencode({'q':query})[2:]);tracks=response['tracks'];assert tracks;results[:]=tracks
        return {'results':len(tracks),'sources':sorted({str(item.get('source','')) for item in tracks})}
    check('search-normal',lambda:search('Ed Sheeran Shape of You'))
    check('search-cached',lambda:search('Ed Sheeran Shape of You'))
    time.sleep(3.1);check('search-misspelling',lambda:search('Джефф Лорбер'))
    chart=api('/api/charts?country=de');assert chart.get('tracks')
    check('charts-de',lambda:{'tracks':len(chart['tracks']),'updated':chart.get('updated'),'stale':chart.get('stale')})
    check('charts-versions',lambda:{'versions':len(api('/api/charts/resolve',{'country':'de','track':chart['tracks'][0]['id']}).get('tracks',[]))})
    library=api('/api/library');tracks=library.get('tracks',[])+library.get('recent',[]);track=next(item for item in tracks if item.get('playable'))
    identifier=str(track['id'])
    def stream():
        ticket=api('/api/stream',{'track':identifier})
        with urllib.request.urlopen(urllib.request.Request(ticket['url'],headers={'Range':'bytes=0-31'}),timeout=30) as response:assert response.status==206 and len(response.read(32))==32
        return {'range':206}
    check('saved-library-stream',stream)
    check('dj-analysis',lambda:{'peaks':len(api('/api/dj/analysis?track='+identifier)['peaks'])})
    check('dj-projects-read',lambda:{'projects':len(api('/api/dj/projects')['projects'])})
    if results:
        check('lyrics-api',lambda:{'response_keys':sorted(api('/api/lyrics?track='+str(results[0]['id'])).keys())})
    def lyrics():
        import asyncio
        from app_lyrics import shared
        result=asyncio.run(shared.lookup('Shape of You','Ed Sheeran',263));assert result.get('text') or result.get('matches');return {'response_keys':sorted(result)}
    check('lyrics-known-recording',lyrics)
    buffer=io.BytesIO();rate=24000
    with wave.open(buffer,'wb') as audio:
        audio.setparams((1,2,rate,0,'NONE',''));audio.writeframes(b''.join(round(12000*math.sin(n*math.tau*220/rate)).to_bytes(2,'little',signed=True) for n in range(rate*2)))
    profiles=[('mp3',False,['reverb','echo','lofi','normalize','compressor','equalizer','mastering','pro_reverb']),('wav',True,['highpass','lowpass','reverse','tremolo','distortion','stereo','delay'])]
    for format,linked,effects in profiles:
        def render(format=format,linked=linked,effects=effects):
            settings={'format':format,'speed':1.1,'pitch':2,'linked':linked,'bass':2,'treble':1,'effects':effects,'fade':.1,'delivery':'ticket'}
            body,content=multipart(buffer.getvalue(),settings);result=json.loads(request('/api/studio',body,content)[0])
            with urllib.request.urlopen(result['url'],timeout=30) as response:raw=response.read()
            with tempfile.TemporaryDirectory(prefix='audit-audio-') as folder:
                target=Path(folder)/('result.'+format);target.write_bytes(raw)
                probe=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration:stream=codec_name','-of','json',str(target)],check=True,capture_output=True,text=True)
                media=json.loads(probe.stdout);assert float(media['format']['duration'])>1
            return {'format':format,'effects':len(effects),'linked':linked,'bytes':len(raw)}
        check('studio-'+format,render)
    check('voice-transcription',voice_check)
    def recognition():
        if not os.getenv('ACOUSTID_API_KEY'):return {'configured':False,'status':'not-tested-no-key'}
        result=api('/api/recognize',{'source_track':identifier});return {'provider':result.get('provider'),'matches':len(result.get('matches',[]))}
    check('recording-recognition',recognition)
    def db():
        for name in ('STATE_DB_PATH','USERS_DB_PATH'):
            with sqlite3.connect(Path(os.environ[name]).as_uri()+'?mode=ro',uri=True) as connection:assert connection.execute('PRAGMA quick_check').fetchone()[0]=='ok'
        return {'databases':2}
    check('sqlite-integrity',db)
    for index,uid in enumerate(UIDS):check('library-unchanged-account-'+str(index),lambda uid=uid:{'unchanged':fingerprint(api('/api/library',uid=uid))==before[uid]})
    print('No Telegram messages, library writes, or changes to user languages.',flush=True)

if __name__=='__main__':
    if '--voice-only' in sys.argv:check('voice-transcription-retest',voice_check)
    else:main()
