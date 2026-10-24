import sqlite3
import tempfile
import unittest
from pathlib import Path
from state_store import StateStore
from library_ui import all_saved


class PlaylistStorageTests(unittest.TestCase):
    def test_legacy_playlist_only_tracks_remain_visible_without_duplicates(self):
        first = {"id": 1, "title": "One", "artist": "A"}
        second = {"id": 2, "title": "Two", "artist": "B"}
        saved = all_saved(77, {77: [first]}, {"legacy": {"name": "Old", "songs": [first, second]}})
        self.assertEqual([song["id"] for song in saved], [1, 2])

    def test_library_commit_preserves_history_and_is_atomic(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.sqlite"
            store = StateStore(path)
            old = [{"id": 1, "title": "Old", "artist": "A"}]
            store.save(77, ["history"], old)
            store.save_library(77, old, {"first": {"name": "Mix", "songs": old}})
            self.assertEqual(store.load()[0][77], ["history"])
            with sqlite3.connect(path) as db:
                db.execute("CREATE TRIGGER reject_library BEFORE INSERT ON named_state WHEN NEW.name='music_collections' BEGIN SELECT RAISE(ABORT, 'test failure'); END")
            with self.assertRaises(sqlite3.IntegrityError):
                store.save_library(77, [], {})
            self.assertEqual(store.load()[1][77], old)
            self.assertIn("first", store.load_named("music_collections")[77])
