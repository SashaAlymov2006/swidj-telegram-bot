import asyncio
import unittest
from unittest.mock import patch,AsyncMock
from types import SimpleNamespace as NS
from tests import test_miniapp as fixtures
from versions import source_search,_source_checks,_source_metadata,source_inventory

YT={'title':'Song','artist':'Artist','url':'https://www.youtube.com/watch?v=abcdefghijk','duration':180}
SC=dict(YT,url='https://soundcloud.com/artist/song')

class CheckedReuse(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        _source_checks.clear();_source_metadata.clear()
        self.addCleanup(_source_checks.clear);self.addCleanup(_source_metadata.clear)
    def test_direct_search_reuses_preflight_but_expands_and_keeps_owners_separate(self):
        rows=[dict(SC,url=SC['url']+str(i)) for i in range(5)]
        def verify(items,q,uid,limit):return items[:limit]
        with patch('soundcloud_source.search',return_value=rows) as search,patch('recording_availability.verified_choices',side_effect=verify) as checked:
            song={'_search_query':'Song Artist','_availability_uid':77,'_availability_limit':2}
            first=source_search(song,'sc');first[0]['title']='Caller mutation'
            self.assertEqual(source_search(song,'sc')[0]['title'],'Song')
            self.assertEqual(checked.call_count,1)
            self.assertEqual(len(source_search(dict(song,_availability_limit=5),'sc')),5)
            self.assertEqual(checked.call_count,2);self.assertEqual(search.call_count,1)
            source_search(dict(song,_availability_uid=78),'sc')
            self.assertEqual(checked.call_count,3)
    async def test_skipping_primary_does_not_cache_false_failure(self):
        with patch('versions.source_search',return_value=[]) as search:
            result=await source_inventory({'title':'Song'},77,skip=('yt',))
        self.assertNotIn('yt',result);self.assertNotIn((77,'Song','yt'),_source_checks)
        self.assertNotIn('yt',[call.args[1] for call in search.call_args_list])
    def test_identical_inflight_queries_only_search_once_and_leave_no_locks(self):
        import threading
        from concurrent.futures import ThreadPoolExecutor
        from versions import _inflight_searches
        started=threading.Event();release=threading.Event()
        def search(*args):
            started.set();self.assertTrue(release.wait(2));return [dict(SC)]
        song={'_search_query':'Song Artist','_availability_uid':77}
        with patch('soundcloud_source.search',side_effect=search) as metadata,patch('recording_availability.verified_choices',return_value=[dict(SC)]) as verify,ThreadPoolExecutor(2) as pool:
            first=pool.submit(source_search,song,'sc');self.assertTrue(started.wait(2))
            second=pool.submit(source_search,song,'sc');release.set()
            a,b=first.result(timeout=3),second.result(timeout=3)
            self.assertEqual(a,b);self.assertIsNot(a,b)
            self.assertEqual(metadata.call_count,1);self.assertEqual(verify.call_count,1)
        self.assertFalse(_inflight_searches)
    def test_canceled_query_does_not_leak_coalescing_lock(self):
        from versions import coalesced_search,_inflight_searches
        from operations import Operation,_current,OperationCancelled
        operation=Operation(77);operation.stopped.set();marker=_current.set(operation)
        try:
            with self.assertRaises(OperationCancelled):
                with coalesced_search((77,'Song','sc')):self.fail('Canceled query ran')
        finally:_current.reset(marker)
        self.assertFalse(_inflight_searches)
    def test_chat_operation_owner_is_used_when_uid_not_explicit(self):
        from operations import Operation,_current
        with patch('soundcloud_source.search',return_value=[dict(SC)]),patch('recording_availability.verified_choices',return_value=[dict(SC)]) as checked:
            for uid in (77,78):
                marker=_current.set(Operation(uid))
                try:source_search({'_search_query':'Song Artist'},'sc')
                finally:_current.reset(marker)
        self.assertEqual([call.args[2] for call in checked.call_args_list],[77,78])

class ChartParallelism(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=fixtures.MiniApiTests.asyncSetUp
    async def test_chart_checks_primary_and_other_catalogs_together_without_changing_choices(self):
        worker=self.client.app['charts_worker'];started=asyncio.Event()
        seed={'id':'101','title':'Song','artist':'Artist','query':'Artist Song'}
        async def primary(*args,**kwargs):
            self.assertEqual(kwargs['uid'],77)
            await asyncio.wait_for(started.wait(),2)
            return seed,[dict(YT)]
        async def inventory(song,uid,known=None,*,skip=()):
            self.assertEqual(uid,77)
            if known is None:
                self.assertEqual(skip,('yt',));started.set();return {'sc':[dict(SC)],'jam':[]}
            self.assertIn('yt',known);return {'yt':known['yt']}
        with patch.object(worker,'get',new_callable=AsyncMock,return_value={'tracks':[seed]}),patch.object(worker,'resolve',side_effect=primary),patch('versions.source_inventory',side_effect=inventory):
            response=await self.client.post('/api/charts/resolve',headers=self.headers,json={'country':'de','track':'101'})
            self.assertEqual(response.status,200);result=await response.json()
            self.assertEqual(len(result['tracks']),2)
            self.assertEqual(set(result['available_sources']),{'yt','sc'})
        self.assertEqual(len(self.bridge.favorites[77]),1)
        self.bridge.application.bot.send_message.assert_not_awaited()
    async def test_chart_preflight_uses_owner_and_result_cache_is_owner_scoped(self):
        worker=self.client.app['charts_worker'];seed={'id':'101','title':'Song','artist':'Artist','query':'Artist Song'}
        with patch.object(worker,'get',new_callable=AsyncMock,return_value={'tracks':[seed]}),patch('versions.find_versions',return_value=[dict(YT)]),patch('recording_availability.verified_choices',side_effect=lambda rows,q,uid,limit:rows) as checked:
            await worker.resolve('de','101',self.bridge,uid=77)
            await worker.resolve('de','101',self.bridge,uid=77)
            await worker.resolve('de','101',self.bridge,uid=78)
            self.assertEqual([call.args[2] for call in checked.call_args_list],[77,78])
