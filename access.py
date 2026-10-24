"""Roles and tariff access. Identity comes exclusively from Telegram updates."""
from dataclasses import dataclass


def parse_owner_ids(value):
    result = set()
    for item in value.split(','):
        item = item.strip()
        if not item:
            continue
        if not item.isascii() or not item.isdecimal() or int(item) <= 0:
            raise ValueError('OWNER_USER_IDS must contain comma-separated positive numeric IDs')
        result.add(int(item))
    return frozenset(result)


def telegram_user_id(update):
    user = getattr(update, 'effective_user', None)
    uid = getattr(user, 'id', None)
    return uid if type(uid) is int and uid > 0 else None


@dataclass(frozen=True)
class AccessPolicy:
    owner_ids: frozenset = frozenset()

    def is_owner(self, update):
        uid = telegram_user_id(update)
        return uid is not None and uid in self.owner_ids

    def allowed(self, update, *, paid, subscription_active, system_allowed):
        # Load limits, provider budgets and global disable always take priority.
        if not system_allowed or telegram_user_id(update) is None:
            return False
        return self.is_owner(update) or not paid or subscription_active
