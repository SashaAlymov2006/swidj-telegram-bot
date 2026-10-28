"""Controlled fallback checks in this process only; no production fault injection."""
import asyncio,json,os,sys,tempfile,time
from pathlib import Path
from unittest.mock import patch
from operations import Operation,_current
from scratch import scratch_root,remove_owned_file
from miniapp_studio import probe
import bot,app_media,yt_dlp
from media_recovery import download_with_reserve
from video_presentation import probe_video

def main():
    uid=int(os.environ['OWNER_USER_IDS'].split(',')[0]);marker=_current.set(Operation(uid))
    try:
        with tempfile.TemporaryDirectory(dir=scratch_root(),prefix='controlled-reserve-') as folder,patch.dict(os.environ,DOWNLOAD_CACHE_DIR=str(Path(folder)/'cache')):
            def unavailable(*args,**kwargs):raise RuntimeError('Controlled test-process primary outage')
            start=time.monotonic();path=None
            try:
                path,info=download_with_reserve(unavailable,'https://www.youtube.com/watch?v=QAaudio0001',{'title':'Flickermood','artist':'Forss','duration':213.94},uid=uid)
                assert info.get('source')=='SoundCloud'
                print(json.dumps({'check':'soundcloud-reserve','ok':True,'bytes':Path(path).stat().st_size,'duration':round(asyncio.run(probe(path)),2),'seconds':round(time.monotonic()-start,2)}),flush=True)
            except Exception as error:print(json.dumps({'check':'soundcloud-reserve','ok':False,'error':type(error).__name__}),flush=True)
            finally:
                if path:remove_owned_file(path)
            url='https://www.youtube.com/watch?v=jNQXAC9IVRw'
            for flow in ('chat','miniapp'):
                if '--miniapp-only' in sys.argv and flow!='miniapp':continue
                start=time.monotonic()
                try:
                    with tempfile.TemporaryDirectory(dir=folder) as work:
                        if flow=='chat':
                            with patch.object(bot,'_extract_media',side_effect=yt_dlp.utils.DownloadError('Controlled primary unavailable')),patch.object(bot,'scratch_root',return_value=Path(work)):
                                path=bot.download_youtube_video(url,1080)
                            assert getattr(path,'quality_limit',None)==720
                            media=probe_video(path)
                        else:
                            with patch.object(yt_dlp.YoutubeDL,'extract_info',side_effect=yt_dlp.utils.DownloadError('Controlled primary unavailable')):
                                result=app_media.fetch({'url':url,'mode':'video','height':1080},Path(work))
                            assert result.get('video_quality_limit')==720
                            path=result['path'];media=probe_video(path)
                        assert 15<float(media['duration'])<25
                        print(json.dumps({'check':'video-reserve-'+flow,'ok':True,'bytes':Path(path).stat().st_size,'duration':media['duration'],'quality_limit':720,'seconds':round(time.monotonic()-start,2)}),flush=True)
                except Exception as error:
                    print(json.dumps({'check':'video-reserve-'+flow,'ok':False,'error':type(error).__name__}),flush=True)
    finally:_current.reset(marker)

if __name__=='__main__':main()
