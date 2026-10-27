import unittest


class RecordingSourceLabels(unittest.TestCase):
    def test_source_button_labels_are_translated(self):
        from i18n_ui import english
        self.assertEqual(english('Версии SoundCloud'),'SoundCloud recordings')
        self.assertEqual(english('Версии Jamendo'),'Jamendo recordings')
        self.assertEqual(english('Версии YouTube'),'YouTube recordings')
from types import SimpleNamespace
from i18n_ui import english, localized_data, locale, action

class LocalizationTests(unittest.TestCase):
    def test_all_major_ui_surfaces(self):
        pairs={
            "🔎 Как ищем?":"How would you like to search?",
            "Не удалось скачать трек. Попробуй ещё раз или выбери другую версию.":"Could not download the track.",
            "🔔 <b>Рингтон</b>\nС 0:45 · до 30 сек.\n\nВыбери формат файла:":"Ringtone",
            "🎵 <b>Здесь будут твои треки</b>\nНайди песню или отправь свой файл и нажми «＋ Сохранить».":"Your tracks will appear here",
            "📊 Пользователей: 12\nАктивных задач: 2\nРаботает: 5 мин":"Users:",
            "✓ Очередь завершена · отправлено 3 из 5 · пропущено 2":"Queue complete",
            "✨ <b>Ремикс и рингтон</b>\nВыбери готовый вариант:":"Choose a preset",
            "❌ У тебя нет доступа к этой команде.":"You do not have access",
        }
        for text,expected in pairs.items():
            with self.subTest(text=text):
                translated=english(text)
                self.assertIn(expected,translated)
                self.assertFalse(any("\u0400" <= char <= "\u04ff" for char in translated),translated)

    def test_song_artist_playlist_and_transcript_content_is_unchanged(self):
        caption="🎵 <b>Студия</b>\nОтмена\n\n♪ SwiDJ"
        self.assertEqual(english(caption),caption)
        self.assertIn("<b>Поиск</b>",english("🎧 <b>Поиск</b> · 2"))
        self.assertIn("Сохранить Отмена",english("📝 Сохранить Отмена\n\nИскать по этим словам?"))
        marker=locale.set("en")
        try:
            data=localized_data("sendMessage",{"text":"Готово","reply_markup":{"inline_keyboard":[
                [{"text":"Студия","callback_data":"lib:col:abc"}],
                [{"text":"＋ Сохранить","callback_data":"track:save:abc"}]]}})
            self.assertEqual(data["reply_markup"]["inline_keyboard"][0][0]["text"],"Студия")
            self.assertEqual(data["reply_markup"]["inline_keyboard"][1][0]["text"],"＋ Save")
            self.assertEqual(data["reply_markup"]["inline_keyboard"][1][0]["callback_data"],"track:save:abc")
        finally:locale.reset(marker)

    def test_user_lyrics_broadcasts_and_media_fields_are_not_translated(self):
        marker=locale.set("en")
        try:
            for tag in ("lyrics_1","admin_send"):
                token=action.set(tag)
                try:
                    self.assertEqual(localized_data("sendMessage",{"text":"Студия Отмена"})["text"],"Студия Отмена")
                finally:action.reset(token)
            data=localized_data("sendAudio",{"title":"Студия","performer":"Отмена","audio":b"original",
                "caption":"🎵 <b>Студия</b>\nОтмена"})
            self.assertEqual(data["title"],"Студия")
            self.assertEqual(data["performer"],"Отмена")
            self.assertEqual(data["audio"],b"original")
        finally:locale.reset(marker)

    def test_russian_remains_unchanged(self):
        marker=locale.set("ru")
        try:
            data={"text":"Моя музыка","reply_markup":{"inline_keyboard":[]}}
            self.assertIs(localized_data("sendMessage",data),data)
        finally:locale.reset(marker)

    def test_retry_and_lyrics_buttons_in_both_languages(self):
        buttons={"inline_keyboard":[
            [{"text":"🔄 Повторить","callback_data":"ver:pick:abc:0"}],
            [{"text":"📄 Текст","url":"https://genius.com/search?q=Song"}],
            [{"text":"Студия","callback_data":"ver:pick:abc:1"}]]}
        for language,expected in (("ru",("🔄 Повторить","📄 Текст")),("en",("🔄 Retry","📄 Lyrics"))):
            marker=locale.set(language)
            try:
                result=localized_data("editMessageText",{"reply_markup":buttons})["reply_markup"]["inline_keyboard"]
                self.assertEqual([result[i][0]["text"] for i in (0,1)],list(expected))
                self.assertEqual(result[0][0]["callback_data"],"ver:pick:abc:0")
                self.assertEqual(result[2][0]["text"],"Студия")
            finally:locale.reset(marker)
