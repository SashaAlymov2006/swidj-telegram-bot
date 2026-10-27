import unittest
from unittest.mock import Mock,patch
from tests import test_miniapp as fixtures
from urllib.parse import urlencode
from search_quality import assisted_search,query_alternative,merge_results,recording_choices

class AssistanceTests(unittest.TestCase):
    def test_phonetic_examples_and_layout(self):
        for query,expected in [('шейп оф ю','shape of you'),('блайндинг лайтс','blinding lights'),('ай вонт ит зэт вэй','i want it that way'),('руддщ','hello')]:
            self.assertEqual(query_alternative(query),expected)
        self.assertIsNone(query_alternative('https://soundcloud.com/artist/song'))
        self.assertIsNone(query_alternative('ю'))
    def test_exact_original_is_not_changed_or_requeried(self):
        rows=[dict(title='Шейп оф ю',artist='Автор',url='original')]
        search=Mock(return_value=rows)
        self.assertIs(assisted_search(search,'шейп оф ю'),rows)
        search.assert_called_once_with('шейп оф ю')
    def test_multilingual_phonetic_candidates(self):
        for query,expected in [('дойчланд','deutschland'),('жё тэм','je taime'),('ласшате ми кантаре','lasciatemi cantare'),('воларе','volare'),('деспасито','despacito'),('rbyj','кино')]:
            self.assertEqual(query_alternative(query),expected)
        self.assertEqual(query_alternative('Джефф Лорбер'),'jeff lorber')
        self.assertEqual(query_alternative('Джаз'),'jaz')
    def test_multilingual_results_are_accepted_with_accents_and_spacing(self):
        for query,title in [('дойчланд','Deutschland'),('жё тэм','Je t’aime'),('ласшате ми кантаре','Lasciatemi cantare'),('деспасито','Despacito'),('rbyj','Кино')]:
            search=Mock(side_effect=[[],[dict(title=title,artist='Artist',url='found')]])
            self.assertEqual(assisted_search(search,query)[0]['title'],title)
    def test_real_russian_and_exact_foreign_names_remain_original(self):
        for query in ('Кино Группа крови','Je t’aime','Deutschland','Lasciatemi cantare','Shape of You'):
            row=dict(title=query,artist='Artist',url='original');search=Mock(return_value=[row])
            self.assertEqual(assisted_search(search,query),[row]);search.assert_called_once_with(query)
    def test_corrected_hits_are_added_but_originals_kept(self):
        original=dict(title='Other song',artist='Another artist',url='old')
        right=dict(title='Shape of You',artist='Ed Sheeran',url='right')
        search=Mock(side_effect=[[original],[right,dict(title='Wrong',artist='Nobody',url='wrong')]])
        rows=assisted_search(search,'шейп оф ю',10)
        self.assertEqual([r['url'] for r in rows],['right','old'])
        self.assertEqual(right,dict(title='Shape of You',artist='Ed Sheeran',url='right'))
        self.assertEqual(recording_choices(rows,'шейп оф ю')[0]['url'],'right')
        self.assertEqual(merge_results([rows],'шейп оф ю')[0]['url'],'right')
    def test_latin_typo_ranks_close_catalog_results_without_extra_requests(self):
        rows=[dict(title='Hello',artist='Nobody'),dict(title='Shape of You',artist='Ed Sheeran')]
        search=Mock(return_value=rows)
        self.assertEqual(assisted_search(search,'Ed Sheran Shape of Yu')[0]['artist'],'Ed Sheeran')
        search.assert_called_once()
    def test_failed_fallback_keeps_previous_result(self):
        rows=[dict(title='Other song',artist='Somebody')]
        self.assertIs(assisted_search(Mock(side_effect=[rows,RuntimeError()]),'шейп оф ю'),rows)
    def test_phonetic_words_inside_unrelated_title_do_not_block_fallback(self):
        search=Mock(side_effect=[[dict(title='Подкаст про шейп оф ю',artist='Someone',url='old')],[dict(title='Shape of You',artist='Ed Sheeran',url='right')]])
        self.assertEqual(assisted_search(search,'шейп оф ю')[0]['url'],'right')
    def test_bot_and_miniapp_source_path_share_assistance(self):
        import bot,asyncio
        with patch('bot._search_songs_sync',side_effect=[[],[dict(title='Shape of You',artist='Ed Sheeran',url='song')]]) as search:
            self.assertEqual(asyncio.run(bot.search_songs('шейп оф ю'))[0]['title'],'Shape of You')
            self.assertEqual(search.call_count,2)
        from versions import source_search,_source_metadata,_source_checks
        _source_metadata.clear();_source_checks.clear()
        with patch('soundcloud_source.search',side_effect=[[],[dict(title='Shape of You',artist='Ed Sheeran',url='https://soundcloud.com/artist/song')]]),patch('recording_availability.available',return_value=True):
            rows=source_search({'_search_query':'шейп оф ю'},'sc')
            self.assertEqual(rows[0]['title'],'Shape of You')
        _source_metadata.clear();_source_checks.clear()

class AssistedMiniApi(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=fixtures.MiniApiTests.asyncSetUp
    async def test_phonetic_search_and_cached_result_preserve_library_for_both_languages(self):
        for language,query in [('ru','шейп оф ю'),('en','жё тэм')]:
            self.bridge.search_times.clear()
            self.bridge.application.user_data[77]['language']=language
            expected='Shape of You' if language=='ru' else 'Je t’aime'
            row=dict(title=expected,artist='Artist',url='https://soundcloud.com/artist/'+language)
            with patch('soundcloud_source.search',side_effect=[[],[row]]) as search:
                path='/api/search?'+urlencode({'q':query,'source':'sc'})
                response=await self.client.get(path,headers=self.headers)
                self.assertEqual(response.status,200);data=await response.json()
                self.assertEqual(data['tracks'][0]['title'],expected)
                cached=await(await self.client.get(path,headers=self.headers)).json()
                self.assertEqual(cached['tracks'],data['tracks']);self.assertEqual(search.call_count,2)
            self.assertEqual(len(self.bridge.favorites[77]),1)
        self.bridge.application.bot.send_message.assert_not_awaited()
