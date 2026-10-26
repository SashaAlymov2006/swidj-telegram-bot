import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch
from telegram.error import BadRequest
from track_card import show_card, selected_song, card_keyboard, retire_download_menus

class TrackCardTests(unittest.IsolatedAsyncioTestCase):
    async def test_app_studio_button_keeps_chat_actions_and_selected_track(self):
        context=NS(user_data={'language':'en'})
        with patch.dict('os.environ',{'MINIAPP_ENABLED':'true','MINIAPP_URL':'https://app.example.test/'}):
            markup=card_keyboard(context,{'id':123,'title':'Track'})
        buttons=[button for row in markup.inline_keyboard for button in row]
        link=next(button for button in buttons if button.web_app)
        self.assertEqual(link.text,'Studio in app')
        self.assertEqual(link.web_app.url,'https://app.example.test/?track=123#studio')
        self.assertTrue(any(button.callback_data and ':studio:' in button.callback_data for button in buttons))
        self.assertEqual(context.user_data['track_cards'][buttons[0].callback_data.rsplit(':',1)[-1]]['id'],123)

    def fixture(self, message=None):
        query = NS(message=message, edit_message_media=AsyncMock(), edit_message_caption=AsyncMock(),
                   edit_message_text=AsyncMock()) if message else None
        update = NS(callback_query=query,effective_chat=NS(id=77))
        context = NS(user_data={},bot=NS(send_photo=AsyncMock(),send_message=AsyncMock()))
        return update,context

    async def test_cover_and_escaped_short_caption(self):
        update,context=self.fixture()
        song={"id":1,"title":"<Song>","artist":"A & B","cover":"https://i.ytimg.com/a.jpg"}
        with patch("track_card.fetch_cover",return_value=b"jpeg"):
            await show_card(update,context,song)
        context.bot.send_photo.assert_awaited_once()
        caption=context.bot.send_photo.call_args.kwargs["caption"]
        self.assertIn("&lt;Song&gt;",caption)
        self.assertIn("A &amp; B",caption)
        self.assertEqual(len(context.bot.send_photo.call_args.kwargs["reply_markup"].inline_keyboard),5)

    async def test_new_song_replaces_cover_in_existing_photo_card(self):
        update,context=self.fixture(NS(photo=[True],text=None))
        with patch("track_card.fetch_cover",return_value=b"new-cover"):
            await show_card(update,context,{"id":2,"title":"Next","cover":"https://i.ytimg.com/b.jpg"})
        update.callback_query.edit_message_media.assert_awaited_once()
        update.callback_query.edit_message_caption.assert_not_awaited()

    async def test_rejected_cover_falls_back_to_text(self):
        update,context=self.fixture()
        context.bot.send_photo.side_effect=BadRequest("photo rejected")
        with patch("track_card.fetch_cover",return_value=b"jpeg"):
            await show_card(update,context,{"id":1,"title":"Track","cover":"https://i.ytimg.com/a.jpg"})
        context.bot.send_message.assert_awaited_once()

    async def test_save_confirmation_reuses_card_without_refetch(self):
        update,context=self.fixture(NS(photo=[True],text=None))
        with patch("track_card.fetch_cover") as fetch:
            await show_card(update,context,{"id":1,"title":"Song"},saved=True,notice="Saved")
            fetch.assert_not_called()
        update.callback_query.edit_message_caption.assert_awaited_once()

    def test_old_actions_are_snapshot_bound_and_capped(self):
        context=NS(user_data={})
        song={"id":1,"title":"Original"}
        keyboard=card_keyboard(context,song)
        callback=keyboard.inline_keyboard[0][0].callback_data
        song["title"]="Changed"
        self.assertEqual(selected_song(context,callback)[1]["title"],"Original")
        self.assertEqual(selected_song(NS(user_data={}),callback),(None,None))
        for index in range(45):
            card_keyboard(context,{"id":index})
        self.assertEqual(len(context.user_data["track_cards"]),40)
        self.assertEqual(selected_song(context,callback),(None,None))

    def test_delivered_audio_has_only_save_playlist_and_studio(self):
        context=NS(user_data={"search_pages":{"abcdef1234":[{"id":1},{"id":2}]}})
        song={"id":1,"_search_page":["abcdef1234",0]}
        keyboard=card_keyboard(context,song,delivered=True)
        payload=str(keyboard.to_dict())
        self.assertNotIn("track:listen:",payload)
        self.assertNotIn("srch:",payload)
        self.assertEqual(len(keyboard.inline_keyboard),3)
        self.assertIn("track:save:",payload)
        self.assertIn("track:studio:",payload)

    async def test_next_result_from_audio_player_is_a_new_downloadable_card(self):
        update,context=self.fixture(NS(photo=[],text=None,audio=True,voice=None,document=None))
        with patch("track_card.fetch_cover",return_value=None):
            await show_card(update,context,{"id":2,"title":"Next song"})
        kwargs=context.bot.send_message.call_args.kwargs
        self.assertIn("track:listen:",str(kwargs["reply_markup"].to_dict()))

    async def test_menu_cleanup_never_targets_another_chat_or_user_message(self):
        update,context=self.fixture(NS(message_id=7,from_user=NS(is_bot=False)))
        context.bot.delete_message=AsyncMock()
        context.bot.edit_message_reply_markup=AsyncMock()
        await retire_download_menus(update,context,{"menu_messages":[[99,10],[77,11]]})
        context.bot.delete_message.assert_awaited_once_with(77,11)

    async def test_text_card_can_gain_cover_without_new_message(self):
        update,context=self.fixture(NS(photo=[],text="Old result"))
        with patch("track_card.fetch_cover",return_value=b"cover"):
            await show_card(update,context,{"id":2,"title":"Next","cover":"https://i.ytimg.com/b.jpg"})
        update.callback_query.edit_message_media.assert_awaited_once()
        context.bot.send_message.assert_not_awaited()
        context.bot.send_photo.assert_not_awaited()

    async def test_photo_without_next_cover_is_replaced_and_old_card_removed(self):
        update,context=self.fixture(NS(photo=[True],text=None,message_id=9,from_user=NS(is_bot=True)))
        context.bot.delete_message=AsyncMock()
        with patch("track_card.fetch_cover",return_value=None):
            await show_card(update,context,{"id":2,"title":"Next"})
        context.bot.send_message.assert_awaited_once()
        context.bot.delete_message.assert_awaited_once_with(77,9)

    async def test_failed_replacement_does_not_delete_previous_card(self):
        update,context=self.fixture(NS(photo=[True],text=None,message_id=9,from_user=NS(is_bot=True)))
        context.bot.delete_message=AsyncMock()
        context.bot.send_message.side_effect=BadRequest("send failed")
        with patch("track_card.fetch_cover",return_value=None),self.assertRaises(BadRequest):
            await show_card(update,context,{"id":2,"title":"Next"})
        context.bot.delete_message.assert_not_awaited()

    async def test_saving_delivered_audio_does_not_restore_variant_controls_or_counter(self):
        message=NS(photo=[],text=None,audio=True,voice=None,document=None)
        update,context=self.fixture(message)
        context.user_data["search_pages"]={"abcdef1234":[{"id":1},{"id":2}]}
        await show_card(update,context,{"id":1,"title":"Song","_search_page":["abcdef1234",0]},saved=True,notice="Saved")
        kwargs=update.callback_query.edit_message_caption.call_args.kwargs
        self.assertNotIn("srch:",str(kwargs["reply_markup"].to_dict()))
        self.assertNotIn("track:listen:",str(kwargs["reply_markup"].to_dict()))
        self.assertNotIn("1 из 2",kwargs["caption"])
        context.bot.send_message.assert_not_awaited()


    async def test_lyrics_button_uses_song_page_or_encoded_search(self):
        context=NS(user_data={})
        song={"id":1,"title":"Song & more","artist":"Artist","url":"https://genius.com/artist-song-lyrics"}
        rows=card_keyboard(context,song).inline_keyboard
        self.assertEqual(rows[-1][0].url,song["url"])
        song["url"]="https://example.com/track"
        self.assertEqual(card_keyboard(context,song).inline_keyboard[-1][0].url,"https://genius.com/search?q=Song%20%26%20more%20Artist")
        self.assertTrue(all(not b.url for row in card_keyboard(context,song,delivered=True).inline_keyboard for b in row))
