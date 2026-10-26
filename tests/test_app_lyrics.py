import unittest
from app_lyrics import search_labels,lyric_matches


class LyricsLookupTests(unittest.TestCase):
    def test_youtube_artist_prefix_and_recording_labels_are_cleaned(self):
        self.assertEqual(search_labels('Ed Sheeran - Shape of You (Official Music Video)','Ed Sheeran - Topic'),('Shape of You','Ed Sheeran'))
        self.assertEqual(search_labels('Song (slowed + reverb)','Artist'),('Song','Artist'))

    def test_real_hyphenated_title_is_not_mistaken_for_artist(self):
        self.assertEqual(search_labels('Love - Hate','Artist'),('Love - Hate','Artist'))

    def test_synced_only_lyrics_are_readable_and_duplicates_removed(self):
        record={'trackName':'Song','artistName':'Artist','plainLyrics':None,'syncedLyrics':'[00:01.20]First fixture line\n[01:02]Second fixture line'}
        result=lyric_matches([None,record,dict(record),{'trackName':'Instrumental','plainLyrics':None}])
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['text'],'First fixture line\nSecond fixture line')

    def test_plain_text_is_preserved_and_size_is_bounded(self):
        result=lyric_matches([{'trackName':'Song','artistName':'Artist','plainLyrics':'x'*65000}])
        self.assertEqual(len(result[0]['text']),64000)
