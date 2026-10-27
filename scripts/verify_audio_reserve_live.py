import json,os
from pathlib import Path
from soundcloud_source import matching_track
from media_recovery import download_with_reserve
from scratch import remove_owned_file
os.environ.pop('DOWNLOAD_CACHE_DIR',None)
hint={'title':'Flickermood','artist':'Forss','duration':213.902}
def unavailable(_):raise RuntimeError('Intentional offline primary fixture')
path=None
try:
 path,info=download_with_reserve(unavailable,'https://www.youtube.com/watch?v=SCFALLBACK1',hint)
 assert info.get('source')=='SoundCloud' and info['duration']>200
 print(json.dumps({'forced_primary_outage_real_reserve':info.get('source'),'bytes':Path(path).stat().st_size,'duration':round(info['duration'],2),'full_audio':info['duration']>200}),flush=True)
finally:
 if path:remove_owned_file(path)
