import unittest
from unittest.mock import patch,AsyncMock
from types import SimpleNamespace as NS
import expanded_catalog as catalogs
import release_catalog
from tests.test_release_catalog import header,song
from tests import test_miniapp as fixtures

ARTIST='11111111-1111-1111-1111-111111111111'
GROUP='22222222-2222-2222-2222-222222222222'
RELEASE='33333333-3333-3333-3333-333333333333'
TRACK='44444444-4444-4444-4444-444444444444'


class ExpandedCatalogTests(unittest.TestCase):
    def setUp(self):
        catalogs._cache.clear();catalogs._known.clear()
        release_catalog._views.clear();self.addCleanup(release_catalog._views.clear)
        self.addCleanup(catalogs._cache.clear);self.addCleanup(catalogs._known.clear)

    def test_parallel_metadata_requests_share_one_upstream_and_do_not_share_mutable_results(self):
        from concurrent.futures import ThreadPoolExecutor
        import threading,time
        calls=[];entered=threading.Event();release=threading.Event()
        def fetch():calls.append(1);entered.set();release.wait(2);return {'items':[1]}
        with ThreadPoolExecutor(max_workers=3) as pool:
            first=pool.submit(catalogs.cached,('test',1),fetch);self.assertTrue(entered.wait(1))
            others=[pool.submit(catalogs.cached,('test',1),fetch) for _ in range(2)]
            time.sleep(.02);release.set();results=[first.result()]+[f.result() for f in others]
        self.assertEqual(len(calls),1);results[0]['items'].append(2);self.assertEqual(results[1]['items'],[1])

    def test_musicbrainz_retries_temporary_unavailability_without_dropping_the_catalog(self):
        import requests
        response=NS(status_code=503)
        with patch('expanded_catalog._mb_at',0),patch('expanded_catalog.get_json',side_effect=[requests.HTTPError(response=response),{'artists':[]}]) as fetch:
            self.assertEqual(catalogs.mb('artist',query='Temporary')['artists'],[])
        self.assertEqual(fetch.call_count,2)

    def test_verified_alias_expands_catalog_but_ambiguous_name_is_not_assumed(self):
        row={'id':ARTIST,'name':'Kanye West','aliases':[{'name':'Ye','locale':'en','type':'Artist name'}]}
        with patch('expanded_catalog.mb',side_effect=[{'artists':[row]},dict(row)]):
            self.assertEqual(catalogs.identity('Kanye West')['id'],ARTIST)
        self.assertIn('Ye',catalogs.known_names('Kanye West'))
        self.assertIn('Ye',catalogs.browse_names({'artist':'Kanye West'}))
        other=dict(row,id=GROUP,name='Ye')
        with patch('expanded_catalog.mb',return_value={'artists':[row,other]}):self.assertIsNone(catalogs.identity('Ye'))

    def test_release_union_deduplicates_same_release_and_preserves_deluxe_and_new_album(self):
        a=header();a['collectionName']='Release'
        extras=[{'id':'mb-'+GROUP,'title':'Release','artist':'Artist','artist_id':'mb-'+ARTIST,'kind':'album','release_date':'2026-10-20','cover':'','source':'MusicBrainz','source_url':'https://musicbrainz.org/release-group/'+GROUP},
                {'id':'jam-12','title':'Release (Deluxe)','artist':'Artist','kind':'album','release_date':'2026-10-21','source':'Jamendo','source_url':'https://www.jamendo.com/list/a12'},
                {'id':'aud-abc','title':'Newest','artist':'Artist','kind':'album','release_date':'2026-10-29','source':'Audius','source_url':'https://audius.co/artist/album/newest'}]
        with patch('release_catalog._request',return_value=[a]),patch('release_catalog._additional',return_value=extras):
            page=release_catalog.releases({'artist':'Artist'})
        self.assertEqual(page['total'],3);self.assertEqual(page['releases'][0]['title'],'Newest')
        merged=next(r for r in page['releases'] if r['title']=='Release')
        self.assertEqual(len(merged['alternatives']),2)
        self.assertEqual(set(page['catalogs']),{'Apple Music','MusicBrainz','Jamendo','Audius'})

    def test_explicit_artist_identity_does_not_lose_other_catalogs_to_same_name_profiles(self):
        extra={'id':'mb-'+GROUP,'title':'New album','artist':'Ye','kind':'album','source':'MusicBrainz','source_url':'https://musicbrainz.org/release-group/'+GROUP,'release_date':'2026'}
        def apple(song,**kwargs):
            if song['artist']=='Ye':return {'name':'Ye','releases':[],'profiles':[{'id':'1'},{'id':'2'}],'selected_profile':''}
            return {'name':'Kanye West','releases':[dict(extra,id='9',title='Older',source='Apple Music')],'profiles':[],'selected_profile':''}
        with patch('release_catalog._additional',return_value=[extra]),patch('release_catalog._apple_releases',side_effect=apple):
            page=release_catalog.releases({'artist':'Ye','_mb_artist_id':ARTIST,'_artist_aliases':['Ye','Kanye West']})
        self.assertEqual(set(page['catalogs']),{'MusicBrainz','Apple Music'});self.assertEqual(page['profiles'],[])

    def test_musicbrainz_album_uses_real_disc_order_and_rejects_other_artist(self):
        group={'title':'New album','artist-credit':[{'artist':{'id':ARTIST,'name':'Artist'}}],'releases':[{'id':RELEASE,'status':'Official','country':'US'}]}
        release={'artist-credit':[{'name':'Artist'}],'media':[{'position':1,'tracks':[{'position':1,'title':'Song','recording':{'id':TRACK},'length':180000}]}]}
        with patch('expanded_catalog.mb',side_effect=[group,release]):
            page=catalogs.album({'artist':'Artist','_mb_artist_id':ARTIST},'mb-'+GROUP)
        self.assertEqual(page['tracks'][0]['track_number'],1);self.assertEqual(page['tracks'][0]['duration'],180)
        with patch('expanded_catalog.mb',return_value=group):
            with self.assertRaises(ValueError):catalogs.album({'artist':'Other','_mb_artist_id':RELEASE},'mb-'+GROUP)

    def test_catalog_provider_failure_does_not_remove_other_sources(self):
        row={'id':'jam-1','title':'Indie album'}
        with patch('expanded_catalog._mb_releases',side_effect=ValueError()),patch('expanded_catalog._jam_releases',return_value=[row]),patch('expanded_catalog._aud_releases',return_value=[]):
            self.assertEqual(catalogs.collect({'artist':'Artist'}),[row])

    def test_jamendo_album_preserves_permitted_track_order_and_attribution(self):
        data=[{'id':'12','name':'Indie album','artist_name':'Artist','tracks':[{'id':'34','name':'Song','duration':180,'position':1,
                'audiodownload_allowed':True,'license_ccurl':'https://creativecommons.org/licenses/by/4.0/'}]}]
        with patch('expanded_catalog.jam',return_value=data):page=catalogs.album({'artist':'Artist'},'jam-12')
        self.assertEqual(page['tracks'][0]['track_number'],1);self.assertEqual(page['tracks'][0]['source'],'Jamendo')
        self.assertTrue(page['tracks'][0]['license_url'])

    def test_audius_same_name_accounts_do_not_share_cached_albums(self):
        def api(path,params):
            uid=path.split('/')[2]
            return [{'id':'alb'+uid,'is_album':True,'playlist_name':'Album '+uid,'permalink':'/artist/album-'+uid,'user':{'id':uid,'name':'Artist'}}]
        with patch('audius_source.enabled',return_value=True),patch('audius_source.api',side_effect=api):
            first=catalogs._aud_releases({'artist':'Artist','_audius_user_id':'aaa'})
            second=catalogs._aud_releases({'artist':'Artist','_audius_user_id':'bbb'})
        self.assertNotEqual(first[0]['id'],second[0]['id'])

    def test_album_can_use_the_matching_catalog_copy_if_primary_metadata_fails(self):
        release_catalog._views[('Artist',None,None,())]=(99999999999,{'releases':[{'alternatives':[{'id':'9'},{'id':'mb-'+GROUP}]}]})
        expected={'tracks':[{'title':'Song','artist':'Artist'}]}
        with patch('release_catalog._apple_album',side_effect=ValueError()),patch('expanded_catalog.album',return_value=expected) as backup:
            self.assertEqual(release_catalog.album({'artist':'Artist'},'9'),expected)
        self.assertEqual(backup.call_args.args[1],'mb-'+GROUP)


class ArtistDiscoveryApiTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=fixtures.MiniApiTests.asyncSetUp
    async def test_album_metadata_resolves_public_versions_instead_of_forcing_restricted_source(self):
        raw={'id':123,'title':'Song','artist':'Artist','url':'https://www.jamendo.com/track/123','_catalog_metadata':True}
        self.bridge.catalog_recordings[77]=[raw]
        versions=[{'id':2,'title':'Song','artist':'Artist','url':'https://soundcloud.com/artist/song','duration':180}]
        with patch('versions.catalog_choices',new=AsyncMock(return_value=(versions,{'sc':versions}))),patch.object(self.bridge.audio_jobs,'start') as direct:
            response=await self.client.post('/api/prepare',headers=self.headers,json={'track':'123'})
            data=await response.json();self.assertEqual(response.status,200);self.assertEqual(data['status'],'choices')
            self.assertEqual(data['available_sources'],['sc']);direct.assert_not_called()
    async def test_artist_entities_are_clickable_and_owner_scoped_without_library_writes(self):
        from copy import deepcopy
        before=deepcopy(self.bridge.favorites)
        self.bridge.chart_recordings[77]=[{'id':999,'title':'Existing chart song'}]
        artist={'id':123,'title':'Artist','name':'Artist','artist':'Artist','url':'https://musicbrainz.org/artist/'+ARTIST,
                'source':'MusicBrainz','description':'composer','_mb_artist_id':ARTIST,'_artist_aliases':['Artist','Alias']}
        with patch('expanded_catalog.discover',return_value=[artist]),patch('expanded_catalog.search_albums',return_value=[]):
            response=await self.client.get('/api/artists?q=Artist',headers=self.headers)
            self.assertEqual(response.status,200);data=await response.json();self.assertEqual(data['artists'][0]['id'],'123')
            found=await self.bridge.find(77,'123');self.assertEqual(found['_mb_artist_id'],ARTIST)
            with self.assertRaises(Exception):await self.bridge.find(78,'123')
        self.assertEqual(self.bridge.favorites,before);self.bridge.application.bot.send_message.assert_not_awaited()
        self.assertEqual(self.bridge.chart_recordings[77],[{'id':999,'title':'Existing chart song'}])

class ArtistDiscoveryChatTests(unittest.IsolatedAsyncioTestCase):
    async def test_discovered_artist_opens_existing_catalog_in_both_languages(self):
        from artist_ui import discovery_button,callback
        for language in ('ru','en'):
            context=NS(user_data={'language':language});button=discovery_button(context,'Artist')
            message=NS(edit_text=AsyncMock());query=NS(answer=AsyncMock(),data=button.callback_data,message=message)
            update=NS(callback_query=query,effective_message=message)
            row={'id':123,'name':'Artist','artist':'Artist','title':'Artist','url':'https://musicbrainz.org/artist/'+ARTIST,'source':'MusicBrainz','description':'composer'}
            with patch('expanded_catalog.discover',return_value=[row]):await callback(update,context)
            target=message.edit_text.call_args.kwargs['reply_markup'].inline_keyboard[0][0].callback_data
            self.assertTrue(target.startswith('art:'));self.assertEqual(len(context.user_data['artist_views']),1)
