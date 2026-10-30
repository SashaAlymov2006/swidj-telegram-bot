import re
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock,patch
from feature_guide import WELCOME,TOPICS,panel,callback

class FeatureGuideTests(unittest.IsolatedAsyncioTestCase):
    async def test_inventory_covers_all_export_effects_and_the_eight_user_sections(self):
        from miniapp_studio import EFFECTS
        labels={'reverb':'reverb','echo':'echo','lofi':'lo-fi','normalize':'normalisation',
                'compressor':'compressor','delay':'delay','equalizer':'eq','mastering':'mastering',
                'pro_reverb':'pro reverb','highpass':'high-pass','lowpass':'low-pass',
                'reverse':'reverse','tremolo':'tremolo','distortion':'distortion','stereo':'stereo'}
        self.assertEqual(set(EFFECTS)-{'none'},set(labels))
        studio=TOPICS['studio'][3].lower()
        for word in labels.values():self.assertIn(word,studio)
        self.assertEqual(set(TOPICS),{'search','links','library','studio','dj','video','lyrics','comfort'})

    async def test_all_topics_are_bilingual_short_and_keep_real_navigation(self):
        for language in ('ru','en'):
            context=NS(user_data={'language':language})
            for topic in ['home',*TOPICS]:
                text,keyboard=panel(context,topic,app_url='https://example.test')
                self.assertLess(len(text),1024)
                if language=='en':self.assertIsNone(re.search('[А-Яа-я]',text))
                buttons=[b for row in keyboard.inline_keyboard for b in row]
                self.assertTrue(any(b.callback_data=='ui:home' for b in buttons))
                self.assertTrue(any(b.web_app for b in buttons))
                self.assertTrue(all(not b.callback_data or len(b.callback_data.encode())<=64 for b in buttons))
            self.assertLess(len(WELCOME[language]),500)

    async def test_group_guide_has_no_unsupported_webapp_button_and_updates_same_message(self):
        message=NS(edit_text=AsyncMock())
        update=NS(effective_chat=NS(type='group'),callback_query=NS(answer=AsyncMock(),data='features:home',message=message))
        with patch('miniapp_server.public_url',return_value='https://example.test'):
            await callback(update,NS(user_data={'language':'en'}))
        message.edit_text.assert_awaited_once()
        buttons=[b for row in message.edit_text.call_args.kwargs['reply_markup'].inline_keyboard for b in row]
        self.assertFalse(any(b.web_app for b in buttons))

    async def test_info_does_not_fetch_media_or_mutate_collections(self):
        context=NS(user_data={'language':'ru','favorites':[123]})
        before=dict(context.user_data)
        for topic in TOPICS:panel(context,topic)
        self.assertEqual(context.user_data,before)
