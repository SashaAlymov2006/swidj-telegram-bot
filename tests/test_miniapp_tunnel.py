import unittest
from miniapp_tunnel import replace_url


class TunnelConfigTests(unittest.TestCase):
    def test_rotating_or_removing_url_preserves_other_private_configuration(self):
        original = '# private config\nTELEGRAM_TOKEN=fixture-only\nMINIAPP_URL=https://old.test\nOTHER="keep = this"\n MINIAPP_URL=https://duplicate.test\n'
        updated=replace_url(original,'https://new.trycloudflare.com')
        self.assertEqual(updated.count('MINIAPP_URL='),1)
        self.assertIn('TELEGRAM_TOKEN=fixture-only',updated)
        self.assertIn('OTHER="keep = this"',updated)
        self.assertIn('MINIAPP_URL=https://new.trycloudflare.com',updated)
        self.assertTrue(replace_url(updated,'').endswith('MINIAPP_URL=\n'))
