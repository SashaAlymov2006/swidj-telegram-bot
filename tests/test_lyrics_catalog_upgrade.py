import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock,patch
from aiohttp import web
from app_lyrics import Lyrics,ranked_matches
from lyrics_ui import show,callback

ROW={'id':123,'trackName':'Song','artistName':'Artist','plainLyrics':'First fixture line\nSecond fixture line'}


class LyricsProviders(unittest.IsolatedAsyncioTestCase):
    async def test_exact_lookup_has_source_link_and_cached_result(self):
        service=Lyrics()
        with patch.object(service,'_request',new_callable=AsyncMock,return_value=ROW) as request:
            data=await service.lookup('Artist - Song (Official Audio)','Artist - Topic',180)
            self.assertEqual(data['matches'][0]['source_url'],'https://lrclib.net/api/get/123')
            self.assertEqual(request.call_args.args[2]['duration'],180)
            self.assertEqual(await service.lookup('Song','Artist'),data)
            request.assert_awaited_once()

    async def test_missing_or_failed_primary_uses_second_catalog(self):
        for initial in (None,web.HTTPServiceUnavailable()):
            service=Lyrics()
            calls=[initial,[],{'lyrics':'Another fixture line'}] if initial is None else [initial,{'lyrics':'Another fixture line'}]
            with patch.object(service,'_request',new_callable=AsyncMock,side_effect=calls):
                data=await service.lookup('Song','Artist')
            self.assertEqual(data['matches'][0]['source'],'lyrics.ovh')
            self.assertEqual(data['matches'][0]['source_url'],'https://api.lyrics.ovh/v1/Artist/Song')

    def test_wrong_artist_or_title_is_not_presented_as_match(self):
        rows=[{'title':'Song','artist':'Wrong singer'},{'title':'Different recording','artist':'Artist'},{'title':'Song','artist':'Artist'}]
        self.assertEqual(ranked_matches(rows,'Song','Artist'),rows[-1:])

    async def test_chat_pages_edit_one_message_and_keep_source_in_both_languages(self):
        for language in ('ru','en'):
            context=NS(user_data={'language':language})
            message=NS(reply_text=AsyncMock(),edit_text=AsyncMock())
            query=NS(data='',answer=AsyncMock(),message=message)
            update=NS(effective_message=message,callback_query=query)
            row={'title':'Song','artist':'Artist','text':('Fixture line\n'*600),'source':'LRCLIB','source_url':'https://lrclib.net/api/get/123'}
            with patch('app_lyrics.shared.lookup',new_callable=AsyncMock,return_value={'matches':[row]}):
                await show(update,context,{'title':'Song','artist':'Artist'})
            first=message.reply_text.call_args.kwargs
            self.assertLess(len(first['text']),4096);self.assertIsNone(first['parse_mode'])
            buttons=[b for r in first['reply_markup'].inline_keyboard for b in r]
            self.assertTrue(any(b.url==row['source_url'] for b in buttons))
            next_button=next(b for b in buttons if b.text=='→')
            query.data=next_button.callback_data;await callback(update,context)
            message.reply_text.assert_awaited_once();message.edit_text.assert_awaited_once()


class CatalogChoices(unittest.IsolatedAsyncioTestCase):
    def test_soundcloud_recording_keeps_its_provider_in_public_choices(self):
        from miniapp_server import public_song
        result=public_song({'id':1,'title':'Song','artist':'Artist','url':'https://soundcloud.com/artist/song'})
        self.assertEqual(result['source'],'SoundCloud')

    async def test_general_list_is_five_diverse_choices_and_explicit_source_supports_five(self):
        from versions import catalog_choices,source_search,_source_checks,_source_metadata
        inventory={source:[{'url':f'https://example.test/{source}/{i}','title':'Song','artist':'Artist'} for i in range(3)] for source in ('yt','sc','aud','jam')}
        with patch('versions.source_inventory',new_callable=AsyncMock,return_value=inventory):
            choices,_=await catalog_choices({'title':'Song','artist':'Artist'},77)
        self.assertEqual(len(choices),5);self.assertEqual({r['source'] for r in choices},{'YouTube','SoundCloud','Audius','Jamendo'})
        _source_checks.clear();_source_metadata.clear()
        rows=[{'url':f'https://soundcloud.com/a/song{i}','title':'Song','artist':'Artist'} for i in range(5)]
        with patch('soundcloud_source.search',return_value=rows),patch('recording_availability.verified_choices',side_effect=lambda items,q,uid,limit:items[:limit]):
            self.assertEqual(len(source_search({'title':'Song','artist':'Artist','_availability_limit':5},'sc')),5)
        _source_checks.clear();_source_metadata.clear()
