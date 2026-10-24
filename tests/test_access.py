import unittest
from types import SimpleNamespace
from access import AccessPolicy, parse_owner_ids


def update(uid, username='owner'):
    return SimpleNamespace(effective_user=SimpleNamespace(id=uid, username=username),
                           message=SimpleNamespace(text='123'))


class AccessTests(unittest.TestCase):
    def test_empty_configuration_grants_no_owner(self):
        self.assertFalse(AccessPolicy(parse_owner_ids('')).is_owner(update(123)))

    def test_multiple_owners_by_id_only(self):
        policy = AccessPolicy(parse_owner_ids('123,456'))
        self.assertTrue(policy.is_owner(update(123, 'renamed')))
        self.assertTrue(policy.is_owner(update(456)))
        self.assertFalse(policy.is_owner(update(789, 'owner')))
        self.assertFalse(policy.is_owner(update('123')))
        self.assertFalse(policy.is_owner(SimpleNamespace(effective_user=None)))

    def test_invalid_configuration_fails_closed(self):
        for raw in ['@owner', '-1', '123,abc', '0']:
            with self.assertRaises(ValueError):
                parse_owner_ids(raw)

    def test_owner_bypasses_tariff_but_not_system_limits(self):
        policy = AccessPolicy(frozenset({123}))
        self.assertTrue(policy.allowed(update(123), paid=True, subscription_active=False, system_allowed=True))
        self.assertFalse(policy.allowed(update(123), paid=True, subscription_active=True, system_allowed=False))

    def test_non_owner_needs_active_subscription_only_for_paid_feature(self):
        policy = AccessPolicy(frozenset({123}))
        self.assertFalse(policy.allowed(update(789), paid=True, subscription_active=False, system_allowed=True))
        self.assertTrue(policy.allowed(update(789), paid=True, subscription_active=True, system_allowed=True))
        self.assertTrue(policy.allowed(update(789), paid=False, subscription_active=False, system_allowed=True))

    def test_expired_subscription_does_not_authorize_non_owner(self):
        import tempfile
        from pathlib import Path
        from subscriptions import Plan, SubscriptionLedger
        with tempfile.TemporaryDirectory() as directory:
            ledger = SubscriptionLedger(Path(directory) / 'test.db')
            payload = ledger.create_order(789, Plan('fixture', 7, 100), 1000)
            ledger.confirm(payload, 789, 'XTR', 7, 'charge', 1000)
            policy = AccessPolicy(frozenset({123}))
            for now, expected in [(1099, True), (1100, False)]:
                self.assertEqual(policy.allowed(update(789), paid=True,
                    subscription_active=ledger.active(789, now), system_allowed=True), expected)
