import unittest
from search_quality import merge_results, recording_choices


class SearchQualityTests(unittest.TestCase):
    def test_recording_choices_hide_unrequested_edits_and_limit_originals(self):
        songs=[dict(title='Singer - Song (Official Music Video)',artist='Singer',url='video'),
               dict(title='Singer - Song (Official Audio)',artist='Singer',url='audio'),
               dict(title='Song (Hard Remix)',artist='Singer',url='remix'),
               dict(title='Song (Slowed)',artist='Singer',url='slowed'),
               dict(title='Song (Cover)',artist='Singer',url='cover'),
               dict(title='Song speed up',artist='Singer',url='speedup'),
               dict(title='Song spedup',artist='Singer',url='spedup'),
               dict(title='Song',artist='Singer',url='third'),
               dict(title='Song',artist='Singer',url='fourth')]
        result=recording_choices(songs,'Song Singer')
        self.assertEqual([s['url'] for s in result],['audio','video','third'])
        self.assertIn('remix',[s['url'] for s in recording_choices(songs,'Song Singer ремикс')])
        self.assertIn('cover',[s['url'] for s in recording_choices(songs,'Song Singer cover')])
        self.assertNotIn('slowed',[s['url'] for s in recording_choices(songs,'Song Singer remix')])
        self.assertIn('spedup',[s['url'] for s in recording_choices(songs,'Song Singer speed up')])

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
