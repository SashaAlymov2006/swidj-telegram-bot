"""Offline subscription ledger. No invoices or real charges are created here.

Only the trusted Telegram successful_payment adapter may call confirm().
Plans must be explicitly supplied by the owner; there are no default prices.
"""
import secrets
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Plan:
    code: str
    stars: int
    duration_seconds: int

    def __post_init__(self):
        if not self.code or type(self.stars) is not int or self.stars <= 0:
            raise ValueError("Explicit plan code and positive integer Stars price required")
        if type(self.duration_seconds) is not int or self.duration_seconds <= 0:
            raise ValueError("Positive access duration required")


class SubscriptionLedger:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS orders (
                    payload TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
                    plan TEXT NOT NULL, stars INTEGER NOT NULL,
                    duration INTEGER NOT NULL, created INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS payments (
                    charge TEXT PRIMARY KEY, payload TEXT UNIQUE NOT NULL,
                    user_id INTEGER NOT NULL, starts INTEGER NOT NULL,
                    expires INTEGER NOT NULL);
            ''')

    def _connect(self):
        return sqlite3.connect(self.path, timeout=30)

    def create_order(self, user_id, plan, now):
        payload = secrets.token_urlsafe(24)
        with closing(self._connect()) as db, db:
            db.execute("INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?)",
                       (payload, user_id, plan.code, plan.stars, plan.duration_seconds, now))
        return payload

    @staticmethod
    def _validate(db, payload, user_id, currency, amount):
        row = db.execute("SELECT user_id, stars, duration FROM orders WHERE payload=?", (payload,)).fetchone()
        if row is None or row[0] != user_id or currency != 'XTR' or row[1] != amount:
            raise ValueError("Unknown order, wrong buyer, currency or amount")
        return row

    def precheckout(self, payload, user_id, currency, amount):
        with closing(self._connect()) as db:
            self._validate(db, payload, user_id, currency, amount)
            return db.execute("SELECT 1 FROM payments WHERE payload=?", (payload,)).fetchone() is None

    def confirm(self, payload, user_id, currency, amount, charge, now):
        """Apply one confirmed one-time purchase, atomically and idempotently.

        Manual renewal creates a new order. Recurring Stars subscriptions need
        a separate adapter using Telegram's subscription_expiration_date.
        """
        if not charge:
            raise ValueError("Telegram charge ID required")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = self._validate(db, payload, user_id, currency, amount)
            previous = db.execute("SELECT payload, user_id, expires FROM payments WHERE charge=?", (charge,)).fetchone()
            if previous:
                if previous[:2] != (payload, user_id):
                    raise ValueError("Charge already belongs to another order")
                return previous[2]
            if db.execute("SELECT 1 FROM payments WHERE payload=?", (payload,)).fetchone():
                raise ValueError("Order already paid with another charge")
            until = db.execute("SELECT MAX(expires) FROM payments WHERE user_id=?", (user_id,)).fetchone()[0]
            starts = max(now, until or now)
            expires = starts + row[2]
            db.execute("INSERT INTO payments VALUES (?, ?, ?, ?, ?)",
                       (charge, payload, user_id, starts, expires))
            return expires

    def active(self, user_id, now):
        with closing(self._connect()) as db:
            return db.execute("SELECT 1 FROM payments WHERE user_id=? AND starts<=? AND expires>? LIMIT 1",
                              (user_id, now, now)).fetchone() is not None
