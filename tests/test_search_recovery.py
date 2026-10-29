import tempfile
import time
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock,patch
from search_recovery import remember,lookup,offer
from state_store import StateStore

class SearchRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_bookmarks_survive_snapshot_eviction_and_database_roundtrip(self):
        context=NS(user_data={})
        remember(context,'0123456789','Jeff Lorber','lyrics')
        context.user_data['track_cards']={}
        with tempfile.TemporaryDirectory() as folder:
            store=StateStore(folder+'/state.sqlite3')
            store.save_named('sessions',77,context.user_data)
            restored=NS(user_data=store.load_named('sessions')[77])
        self.assertEqual(lookup(restored,'0123456789')['query'],'Jeff Lorber')
        self.assertEqual(lookup(restored,'0123456789')['mode'],'lyrics')
        self.assertIsNone(lookup(NS(user_data={}), '0123456789'))

    async def test_bounded_bookmarks_expire_and_do_not_fetch_anything(self):
        context=NS(user_data={})
        for n in range(220):remember(context,str(n),'a'*500)
        self.assertEqual(len(context.user_data['search_recovery']),200)
        self.assertEqual(len(lookup(context,'219')['query']),120)
        with patch('search_recovery.time.time',return_value=time.time()+31*86400):
            self.assertIsNone(lookup(context,'219'))

    async def test_track_bookmark_keeps_original_lyric_query_after_another_search(self):
        from track_card import card_keyboard
        context=NS(user_data={'artist_search_query':'Unrelated','search_mode':'title'})
        remember(context,'0123456789','remember these words','lyrics')
        markup=card_keyboard(context,{'id':1,'title':'Song','artist':'Artist','_search_page':['0123456789',0]})
        token=next(b.callback_data.rsplit(':',1)[-1] for row in markup.inline_keyboard for b in row if b.callback_data and b.callback_data.startswith('track:listen:'))
        self.assertEqual(lookup(context,token)['query'],'remember these words')
        self.assertEqual(lookup(context,token)['mode'],'lyrics')

    async def test_expired_cards_offer_one_click_recovery_in_both_languages(self):
        for lang in ('ru','en'):
            context=NS(user_data={'language':lang})
            remember(context,'0123456789','Artist Song')
            message=NS(reply_text=AsyncMock())
            await offer(NS(effective_message=message),context,'0123456789')
            button=message.reply_text.call_args.kwargs['reply_markup'].inline_keyboard[0][0]
            self.assertEqual(button.callback_data,'recover:0123456789')
            self.assertEqual(button.text,'Repeat search' if lang=='en' else 'Повторить поиск')

    async def test_pre_bookmark_photo_can_recover_its_own_song_without_wrong_last_query(self):
        context=NS(user_data={'artist_search_query':'Unrelated query'})
        message=NS(caption='🔎 Вариант 1 из 5\n\n🎵 Shivers\nEd Sheeran',reply_text=AsyncMock())
        await offer(NS(effective_message=message),context,'0123456789')
        target=message.reply_text.call_args.kwargs['reply_markup'].inline_keyboard[0][0].callback_data
        self.assertEqual(lookup(context,target.split(':')[1])['query'],'Ed Sheeran Shivers')

    async def test_recovery_handler_reuses_normal_search_and_restores_real_results(self):
        import bot
        uid=78123123456789
        self.addCleanup(bot.user_search_results.pop,uid,None)
        context=NS(user_data={'language':'en'})
        remember(context,'0123456789','Artist Song')
        message=NS(edit_text=AsyncMock())
        update=NS(effective_user=NS(id=uid),effective_message=message,
                  callback_query=NS(answer=AsyncMock(),data='recover:0123456789'))
        rows=[{'id':1,'title':'Song','artist':'Artist','url':'https://example.com/song'}]
        with patch('bot.search_songs',new=AsyncMock(return_value=rows)),patch('bot.search_deezer',new=AsyncMock(return_value=[])),patch('bot.send_song',new=AsyncMock()) as send:
            await bot.recover_search_callback(update,context)
        self.assertEqual(bot.user_search_results[uid][0]['title'],'Song')
        send.assert_awaited_once_with(update,context)
        self.assertIn('search_recovery',bot.SESSION_KEYS)
