import unittest
from search_quality import merge_results


class SearchQualityTests(unittest.TestCase):
    def test_exact_title_and_artist_outrank_partial_provider_hits(self):
        wrong = {"id": 1, "title": "Hello Again", "artist": "Someone"}
        right = {"id": 2, "title": "Hello", "artist": "Adele"}
        self.assertEqual(merge_results([[wrong, right]], "Adele - Hello"), [right, wrong])

    def test_punctuation_case_and_unicode_do_not_duplicate_tracks(self):
        first = {"id": 1, "title": "Don't Stop", "artist": "BAND"}
        duplicate = {"id": 2, "title": "DON’T STOP", "artist": "band"}
        self.assertEqual(merge_results([[first], [duplicate]]), [first])

    def test_lyrics_without_title_match_keep_provider_order(self):
        songs = [{"title": "A", "artist": "X"}, {"title": "B", "artist": "Y"}]
        self.assertEqual(merge_results([songs], "some remembered lyric"), songs)

    def test_distinct_versions_are_preserved(self):
        songs = [{"title": "Hello", "artist": "Adele"}, {"title": "Hello (Live)", "artist": "Adele"}]
        self.assertEqual(len(merge_results([songs])), 2)
