"""Durable user history and favorites; no network access."""
import json
import sqlite3
from contextlib import closing
from pathlib import Path


def migrate_users(source, destination):
    """Copy legacy users via SQLite backup without overwriting a new DB."""
    source, destination = Path(source), Path(destination)
    if not source.is_file() or destination.exists() or source.resolve() == destination.resolve():
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(source)) as old:
        old.execute('SELECT chat_id FROM users LIMIT 1').fetchall()
        with closing(sqlite3.connect(destination)) as new:
            old.backup(new)
    return True


class StateStore:
    def __init__(self, path):
        self.path = Path(path)

    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=30)
        db.execute("CREATE TABLE IF NOT EXISTS user_state (user_id INTEGER PRIMARY KEY, history TEXT NOT NULL, favorites TEXT NOT NULL)")
        db.execute("CREATE TABLE IF NOT EXISTS named_state (name TEXT NOT NULL, user_id INTEGER NOT NULL, value TEXT NOT NULL, PRIMARY KEY(name, user_id))")
        return db

    def load(self):
        with closing(self._connect()) as db, db:
            rows = db.execute("SELECT user_id, history, favorites FROM user_state").fetchall()
        return ({uid: json.loads(h) for uid, h, _ in rows},
                {uid: json.loads(f) for uid, _, f in rows})

    def save(self, user_id, history, favorites):
        with closing(self._connect()) as db, db:
            db.execute("INSERT INTO user_state VALUES (?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET history=excluded.history, favorites=excluded.favorites",
                       (user_id, json.dumps(history, ensure_ascii=False), json.dumps(favorites, ensure_ascii=False)))

    def load_named(self, name):
        with closing(self._connect()) as db, db:
            rows = db.execute('SELECT user_id, value FROM named_state WHERE name=?', (name,)).fetchall()
        return {uid: json.loads(value) for uid, value in rows}

    def save_named(self, name, user_id, value):
        with closing(self._connect()) as db, db:
            db.execute('INSERT INTO named_state VALUES (?, ?, ?) ON CONFLICT(name, user_id) DO UPDATE SET value=excluded.value',
                       (name, user_id, json.dumps(value, ensure_ascii=False)))

    def save_library(self, user_id, favorites, collections, app_tracks=None, app_recent=None):
        """Commit saved tracks and playlist membership together; preserve search history."""
        with closing(self._connect()) as db, db:
            db.execute("INSERT INTO user_state VALUES (?, '[]', ?) ON CONFLICT(user_id) DO UPDATE SET favorites=excluded.favorites",
                       (user_id, json.dumps(favorites, ensure_ascii=False)))
            db.execute("INSERT INTO named_state VALUES ('music_collections', ?, ?) ON CONFLICT(name, user_id) DO UPDATE SET value=excluded.value",
                       (user_id, json.dumps(collections, ensure_ascii=False)))
            if app_tracks is not None:
                db.execute("INSERT INTO named_state VALUES ('miniapp_library', ?, ?) ON CONFLICT(name, user_id) DO UPDATE SET value=excluded.value",
                           (user_id, json.dumps(app_tracks, ensure_ascii=False)))
            if app_recent is not None:
                db.execute("INSERT INTO named_state VALUES ('miniapp_recent', ?, ?) ON CONFLICT(name, user_id) DO UPDATE SET value=excluded.value",
                           (user_id, json.dumps(app_recent, ensure_ascii=False)))
