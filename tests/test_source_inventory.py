import unittest
from unittest.mock import patch
from versions import source_inventory, source_rows, source_search, _source_checks, _source_metadata

YT = {'url':'https://www.youtube.com/watch?v=abcdefghijk','title':'Song','artist':'Artist'}
SC = {'url':'https://soundcloud.com/artist/song','title':'Song','artist':'Artist'}
JAM = {'url':'https://www.jamendo.com/track/1680810','title':'Song','artist':'Artist'}


class SourceInventoryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        _source_checks.clear()
        _source_metadata.clear()
        self.addCleanup(_source_checks.clear)
        self.addCleanup(_source_metadata.clear)

    async def test_quick_inventory_expands_without_repeating_metadata_search(self):
        rows=[dict(SC,url=SC['url']+str(i)) for i in range(3)]
        with patch('soundcloud_source.search',return_value=rows) as search,patch('recording_availability.available',return_value=True):
            inventory=await source_inventory({'title':'Song','artist':'Artist'},77,{'yt':[],'jam':[]})
            self.assertEqual(len(inventory['sc']),1)
            expanded=source_search({'title':'Song','artist':'Artist','_availability_uid':77},'sc')
        self.assertEqual(len(expanded),3)
        search.assert_called_once_with('Song Artist',10)

    async def test_empty_and_failed_sources_are_not_advertised(self):
        def search(song, source):
            if source == 'jam': raise RuntimeError('offline')
            return [SC] if source == 'sc' else []
        with patch('versions.source_search',side_effect=search):
            inventory=await source_inventory({'title':'Song','artist':'Artist'},77)
        request={'available_sources':[key for key,rows in inventory.items() if rows]}
        buttons=[row[0].callback_data for row in source_rows('token',request)]
        self.assertEqual(buttons,['ver:source:token:sc'])
        request['source']='sc'
        self.assertEqual(source_rows('token',request),[])

    async def test_catalog_query_cache_is_owner_scoped_and_reuses_checked_rows(self):
        song={'title':'Video title','_catalog_song':{'title':'Song','artist':'Artist'}}
        with patch('versions.source_search',return_value=[]) as search:
            first=await source_inventory(song,77,{'sc':[SC]})
            self.assertEqual(search.call_count,2)
            first['sc'][0]['title']='changed by caller'
            second=await source_inventory(song,77)
            self.assertEqual(search.call_count,2)
            self.assertEqual(second['sc'][0]['title'],'Song')
            await source_inventory(song,78)
            self.assertEqual(search.call_count,5)
        with patch('soundcloud_source.search',side_effect=AssertionError('must reuse preflight')):
            self.assertEqual(source_search(dict(song,_availability_uid=77),'sc'),[SC])

    async def test_reserve_rows_do_not_advertise_failed_primary(self):
        with patch('versions.source_search',return_value=[]):
            result=await source_inventory({'title':'Song'},77,{'yt':[SC],'sc':[SC],'jam':[JAM]})
        self.assertEqual(result['yt'],[])
        self.assertEqual(result['sc'],[SC])
        self.assertEqual(result['jam'],[JAM])
        self.assertEqual(source_rows('old',{}),[])
