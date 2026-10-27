# Inline lyrics and recording choices

Chat and Mini App use the same `app_lyrics.Lyrics` service. It first tries LRCLIB's
track signature endpoint, then structured search with artist/title ranking. When no
usable text is found or the primary service fails, it tries the documented lyrics.ovh
API. No speech model, paid service, audio file or Telegram identity is used for lyrics.
Catalog title/artist are preferred for chart recordings. Responses and caches are
bounded, request timeouts and Retry-After are respected. No provider covers every song;
lyrics.ovh itself can use LRCLIB plus other sources, so coverage may overlap.

The chat Lyrics button opens a text message with pages up to 3400 characters, a source
link and an alternative-text button when multiple matches exist. Page clicks edit that
same message. User snapshots are isolated and bounded. Reopening after restart starts
a new lookup. Mini App shows lyrics in its existing dialog, with source and alternative
controls. Sources link to the exact provider record/API response when available, not
an invented Genius page. All text is displayed as escaped/plain text.

The general recording list contains at most five checked choices, combining independent
YouTube, SoundCloud, Audius and Jamendo catalog searches. A selected provider can offer
up to five checked recordings. Empty providers remain hidden; download restrictions
and public/downloadable filters are retained. Good matches are not padded with covers,
unrequested remixes, unavailable entries or unrelated songs. In particular, Audius does
not promise popular-label originals for every query.

Charts now show choices before playback or downloading. An already loaded recording
stays in that choice list and can be reused, while alternative recordings remain
selectable. Source labels identify each recording. Chart artist/title take precedence
over labels and stale queries from a previously selected video.

The YouTube video download chain is unchanged: existing cache and main downloader first;
jaky.dev is only a reserve for failed YouTube video downloads, not a music search catalog.

Provider documentation:
- https://lrclib.net/docs
- https://github.com/NTag/lyrics.ovh
