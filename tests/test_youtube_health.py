import unittest
from unittest.mock import patch, MagicMock
from youtube_health import transition, notify
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace


class YouTubeHealthTests(unittest.TestCase):
    def test_probe_never_rewrites_original_cookie_file(self):
        from youtube_health import probe
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'cookies.txt'
            original='# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t2147483647\tSID\tfixture-session\n'
            source.write_text(original)
            seen=[]
            def factory(options):
                copied=Path(options['cookiefile']);seen.append(copied)
                manager=MagicMock()
                manager.__enter__.return_value.extract_info.return_value={'formats':[{'format_id':'audio'}]}
                manager.__exit__.side_effect=lambda *args:copied.write_text('rewritten cookie jar') and False
                return manager
            with patch.dict(os.environ,YTDLP_COOKIE_FILE=str(source)),patch.dict('sys.modules',{'yt_dlp':SimpleNamespace(YoutubeDL=factory)}):
                self.assertEqual(probe(),'ok')
            self.assertEqual(source.read_text(),original)
            self.assertNotEqual(seen[0],source)

    def test_auth_alert_requires_confirmation_and_does_not_repeat(self):
        first, notice = transition({}, 'auth_required', 1)
        self.assertIsNone(notice)
        second, notice = transition(first, 'auth_required', 2)
        self.assertEqual(notice, 'auth_required')
        third, notice = transition(second, 'auth_required', 3)
        self.assertIsNone(notice)
        healthy, notice = transition(third, 'ok', 4)
        self.assertEqual(notice, 'recovered')
        _, notice = transition(healthy, 'ok', 5)
        self.assertIsNone(notice)

    def test_network_failure_is_not_misreported_as_expired_cookies(self):
        state = {}
        for moment in (1, 2):
            state, notice = transition(state, 'temporary_error', moment)
            self.assertIsNone(notice)
        _, notice = transition(state, 'temporary_error', 3)
        self.assertEqual(notice, 'temporary_error')

    def test_recovery_and_failure_state_survive_restart(self):
        state, _ = transition({}, 'auth_required', 1)
        import json
        restored = json.loads(json.dumps(state))
        _, notice = transition(restored, 'auth_required', 2)
        self.assertEqual(notice, 'auth_required')

    def test_only_configured_owners_receive_sanitized_messages(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"ok":true}'
        with patch('youtube_health.urlopen', return_value=response) as send:
            self.assertEqual(notify('fixture-private-token', [77, 88, 77], 'auth_required'), 2)
        from urllib.parse import parse_qs
        destinations = []
        for call in send.call_args_list:
            payload = parse_qs(call.args[0].data.decode())
            destinations.append(payload['chat_id'][0])
            self.assertNotIn('fixture-private-token', payload['text'][0])
        self.assertEqual(destinations, ['77', '88'])
