"""Supplemental live checks. No messages, account changes or library mutations.

Run inside the existing bot container with PYTHONPATH=/app; full_function_audit.py
must be alongside this script. Temporary media are removed on completion.
"""
import asyncio,io,json,os,subprocess,tempfile,time,urllib.request,wave,math
from pathlib import Path
from urllib.parse import urlencode
from full_function_audit import api,request,multipart,check,UIDS,fingerprint
from operations import Operation,_current
from scratch import remove_owned_file

def main():
    before={uid:fingerprint(api('/api/library',uid=uid)) for uid in UIDS}
    marker=_current.set(Operation(UIDS[0]))
    try:
        import soundcloud_source,audius_source,jamendo_source
        from versions import source_search
        for source,title,artist in [('yt','Never Gonna Give You Up','Rick Astley'),('sc','Flickermood','Forss'),('aud','Set Me Free',''),('jam','piano','')]:
            def search(source=source,title=title,artist=artist):
                rows=source_search({'title':title,'artist':artist,'_availability_limit':3},source)
                assert rows,'No eligible search result'
                return {'eligible_versions':len(rows)}
            check('independent-search-'+source,search)
        # Direct Mini App links for the two additional catalogs, not just chat loaders.
        for name,module,query in [('audius',audius_source,'Set Me Free'),('jamendo',jamendo_source,'piano')]:
            def link(module=module,query=query):
                rows=module.search(query,5);assert rows,'No eligible catalog search result'
                result=api('/api/link',{'url':rows[0]['url'],'mode':'audio'})
                assert result.get('url') and result.get('kind')=='audio'
                with urllib.request.urlopen(urllib.request.Request(result['url'],headers={'Range':'bytes=0-31'}),timeout=30) as response:
                    assert response.status==206 and len(response.read(32))==32
                return {'range':206,'duration':result.get('duration')}
            check('miniapp-direct-link-'+name,link)
        # The speech fixture is generated locally, not captured from the microphone.
        def spoken_search():
            body,content=multipart(Path('/tmp/swidj-voice-fixture.wav').read_bytes())
            text=json.loads(request('/api/voice',body,content)[0])['text'].strip();assert text
            time.sleep(3.1)
            rows=api('/api/search?'+urlencode({'q':text}))['tracks'];assert rows
            return {'transcript_characters':len(text),'results':len(rows)}
        check('miniapp-voice-to-search',spoken_search)
        def known_recording():
            from app_media import download_app_audio
            path,info=download_app_audio('https://www.youtube.com/watch?v=dQw4w9WgXcQ')
            try:
                body,content=multipart(Path(path).read_bytes());result=json.loads(request('/api/recognize',body,content)[0])
                assert result.get('matches'),'Known recording not recognized'
                return {'provider':result.get('provider'),'matches':len(result['matches'])}
            finally:remove_owned_file(path)
        check('recognition-known-recording',known_recording)
        def saved_streams():
            count=0;not_cached=0
            for uid in UIDS:
                tracks=api('/api/library',uid=uid).get('tracks',[])
                for track in tracks:
                    if not track.get('playable'):not_cached+=1;continue
                    ticket=api('/api/stream',{'track':track['id']},uid=uid)
                    with urllib.request.urlopen(urllib.request.Request(ticket['url'],headers={'Range':'bytes=0-65535'}),timeout=30) as response:
                        assert response.status==206 and response.read(32)
                    count+=1
            assert count
            return {'cached_tracks_checked':count,'uncached_library_entries':not_cached}
        check('all-cached-library-streams',saved_streams)
        def artist():
            rows=api('/api/search?'+urlencode({'q':'Jeff Lorber'}))['tracks'];assert rows
            result=api('/api/artist?'+urlencode({'track':rows[0]['id']}))
            assert result.get('tracks');return {'tracks':len(result['tracks'])}
        time.sleep(3.1);check('artist-catalog',artist)
        def charts():
            counts={}
            for country in ('de','gb','us'):
                result=api('/api/charts?'+urlencode({'country':country}));assert result.get('tracks');assert not result.get('stale')
                counts[country]=len(result['tracks'])
            return {'countries':counts}
        check('charts-multiple-countries',charts)
        for index,uid in enumerate(UIDS):
            def unchanged(uid=uid):
                after=fingerprint(api('/api/library',uid=uid))
                # Public tracks include dynamic cache availability. A concurrent
                # user can also keep listening while this read-only audit runs.
                changed=[key for key in before[uid] if before[uid][key]!=after[key]]
                return {'unchanged':not changed,'changed_fields':changed,
                        'before_tracks':len(before[uid].get('tracks') or []),
                        'after_tracks':len(after.get('tracks') or [])}
            check('saved-user-data-unchanged-'+str(index),unchanged)
    finally:_current.reset(marker)

if __name__=='__main__':main()
