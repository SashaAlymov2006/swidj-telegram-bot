import logging
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock
from telegram.error import BadRequest
from diagnostics import classify_error, source_access_blocked
from test_handlers import load_handler


class DiagnosticsTests(unittest.IsolatedAsyncioTestCase):
    def test_source_access_block_is_not_treated_as_transient_download_failure(self):
        for text in ("Sign in to confirm you’re not a bot", "YouTube временно ограничил доступ."):
            self.assertTrue(source_access_blocked(RuntimeError(text)))
        for text in ("Connection timed out", "File too large", "Requested format is not available"):
            self.assertFalse(source_access_blocked(RuntimeError(text)))

    async def test_error_log_and_user_reply_do_not_expose_provider_message(self):
        logger = logging.getLogger('swidj-diagnostic-regression')
        handler = load_handler('error_handler', {'logger': logger, 'classify_error': classify_error})
        secret = '123456:private-token-fixture-must-not-appear'
        context = SimpleNamespace(error=BadRequest("Can't parse entities: " + secret))
        message = SimpleNamespace(reply_text=AsyncMock())
        with self.assertLogs(logger, level='ERROR') as captured:
            await handler(SimpleNamespace(effective_message=message), context)
        self.assertIn('telegram_text_format', captured.output[0])
        self.assertNotIn(secret, ''.join(captured.output))
        self.assertNotIn(secret, message.reply_text.call_args.args[0])

    def test_expired_callback_is_distinguished_from_unknown_bad_request(self):
        self.assertEqual(classify_error(BadRequest('Query is too old and response timeout expired')), 'callback_expired')
        self.assertEqual(classify_error(BadRequest('unknown sensitive provider text')), 'telegram_bad_request_other')
