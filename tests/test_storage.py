import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path

from state_store import StateStore
from state_store import migrate_users
import sqlite3
from subscriptions import Plan, SubscriptionLedger


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'state.sqlite3'

    def test_history_survives_restart_and_clear_is_isolated(self):
        store = StateStore(self.path)
        store.save(1, ['трек'], [{'id': 7, 'title': 'SwiDJ'}])
        store.save(2, ['другой'], [])
        history, favorites = StateStore(self.path).load()
        self.assertEqual(history[1], ['трек'])
        self.assertEqual(favorites[1][0]['title'], 'SwiDJ')
        store.save(1, history[1], [])
        self.assertEqual(store.load(), ({1: ['трек'], 2: ['другой']}, {1: [], 2: []}))

    def test_legacy_users_migration_preserves_existing_destination(self):
        old = Path(self.tmp.name) / 'users.db'
        with closing(sqlite3.connect(old)) as db, db:
            db.execute('CREATE TABLE users (chat_id INTEGER PRIMARY KEY)')
            db.execute('INSERT INTO users VALUES (123)')
        self.assertTrue(migrate_users(old, self.path))
        with closing(sqlite3.connect(self.path)) as db, db:
            self.assertEqual(db.execute('SELECT chat_id FROM users').fetchall(), [(123,)])
            db.execute('INSERT INTO users VALUES (456)')
        self.assertFalse(migrate_users(old, self.path))
        with closing(sqlite3.connect(self.path)) as db, db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM users').fetchone()[0], 2)

    def test_search_results_and_drafts_survive_restart(self):
        store = StateStore(self.path)
        store.save_named('search_results', 1, [{'id': 7, 'title': 'Трек'}])
        store.save_named('broadcast_drafts', 1, {'text': 'Черновик'})
        store.save_named('sessions', 2, {'dl_url': 'https://example.invalid/track'})
        restarted = StateStore(self.path)
        self.assertEqual(restarted.load_named('search_results')[1][0]['title'], 'Трек')
        self.assertEqual(restarted.load_named('broadcast_drafts'), {1: {'text': 'Черновик'}})
        self.assertEqual(set(restarted.load_named('sessions')), {2})

    def test_confirmed_payment_renewal_expiry_and_replay(self):
        ledger = SubscriptionLedger(self.path)
        plan = Plan('fixture', 7, 100)  # Test values, not a product tariff.
        first = ledger.create_order(1, plan, 1000)
        self.assertTrue(ledger.precheckout(first, 1, 'XTR', 7))
        self.assertFalse(ledger.active(1, 1000))
        self.assertEqual(ledger.confirm(first, 1, 'XTR', 7, 'charge1', 1000), 1100)
        self.assertEqual(ledger.confirm(first, 1, 'XTR', 7, 'charge1', 1050), 1100)
        second = ledger.create_order(1, plan, 1050)
        self.assertEqual(ledger.confirm(second, 1, 'XTR', 7, 'charge2', 1050), 1200)
        self.assertTrue(SubscriptionLedger(self.path).active(1, 1199))
        self.assertFalse(ledger.active(1, 1200))
        self.assertFalse(ledger.active(2, 1100))

    def test_reject_mismatch_and_duplicate_order(self):
        ledger = SubscriptionLedger(self.path)
        payload = ledger.create_order(1, Plan('fixture', 7, 100), 1000)
        for uid, currency, amount in [(2, 'XTR', 7), (1, 'EUR', 7), (1, 'XTR', 8)]:
            with self.assertRaises(ValueError):
                ledger.confirm(payload, uid, currency, amount, 'bad', 1000)
        ledger.confirm(payload, 1, 'XTR', 7, 'good', 1000)
        with self.assertRaises(ValueError):
            ledger.confirm(payload, 1, 'XTR', 7, 'other', 1000)

    def test_simultaneous_duplicate_is_applied_once(self):
        ledger = SubscriptionLedger(self.path)
        payload = ledger.create_order(1, Plan('fixture', 7, 100), 1000)
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: ledger.confirm(payload, 1, 'XTR', 7, 'same', 1000), range(8)))
        self.assertEqual(results, [1100] * 8)


if __name__ == '__main__':
    unittest.main()
