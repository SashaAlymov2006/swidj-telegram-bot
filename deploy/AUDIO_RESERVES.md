# Independent audio recovery

Search/voice-search recording downloads use one shared chain:

1. Restore the exact source from the owner's VPS cache or a verified public copy.
2. Recover its saved Telegram file, when available.
3. Download from the selected primary source (normally YouTube).
4. On a YouTube source failure, find a matching public SoundCloud recording.
5. If SoundCloud has no suitable complete recording, try the existing Jamendo reserve.

Direct TikTok/Instagram/video handling stays on its own provider. A failed video
download is never replaced with an unrelated audio file. Direct SoundCloud search
results prepare on SoundCloud; they do not go back through a YouTube lookup.

## Recording identity

Automatic replacement requires a title, performer and duration. Presentation
labels such as “Official Audio” can be removed; remix/live/slowed/cover labels
remain part of the identity. Title and performer must match after conservative
Unicode normalization, and durations must differ by no more than three seconds.
Equal candidates are ambiguous and rejected. SoundCloud can select a uniquely
closer duration within one second when its distance beats the next candidate by
more than 0.25 seconds.

SoundCloud search is anonymous and restricted to its own extractor and canonical
public track URLs. It uses no YouTube cookies. Preview formats are excluded; after
download, metadata and actual FFprobe duration are checked again. A short preview
cannot pass as the full track. Jamendo continues to require allowed downloads and
the existing compatible Creative Commons license checks, with attribution retained.

Known recording metadata can be recovered from the bounded persistent search
cache. SoundCloud/Jamendo search results are also cached for an identical query.
If a fresh opaque YouTube link has no available identity metadata, the system
keeps the original failure rather than guessing a different song. Search and
voice transcription feed the same recording selection/download path.

## Independent recording choices

Exact automatic recovery remains the first attempt. If YouTube rejects the
download, the bot opens a fresh SoundCloud version list using the original
catalog title and performer. The version menus also have explicit SoundCloud
and Jamendo search buttons. Refresh stays on the chosen provider; every list
gets an immutable request snapshot. Already failed/sent versions are omitted
from the other-version list, while an explicit retry remains available.

The Mini App retains the chart/catalog identity separately from the YouTube
video label. After preparation fails it requests `/api/versions` and offers
independent source choices. Failed SoundCloud choices leave the remaining
SoundCloud results available without another search. Jamendo can be selected
from the same dialog. Query text from app text/voice search is retained for
independent searches. The endpoint accepts only a track the authenticated owner
can already access and a fixed provider name; it accepts no arbitrary URLs.

These are visible recording choices, not automatic exact replacements. Covers,
remixes and other uploaders may appear with their titles and performers. The
chosen source URL uses the normal cache/Telegram/download path. Search results
do not guarantee availability: DRM, source access restrictions and missing
catalog recordings can still prevent a download. Searches do not download every
candidate in advance. No new paid service or subscription is connected.

## Public cache and privacy

The existing cache remains bounded by `DOWNLOAD_CACHE_BYTES` and its 30-day LRU
policy. New additive SQLite tables index verified public audio and Telegram IDs.
Legacy cache entries are not automatically declared public. Uploaded/processed
personal audio and secret/private URLs cannot enter the shared index.

SoundCloud publication requires a successful anonymous public-track download;
YouTube publication requires public availability metadata. The shared disk file
has a stored SHA-256 fingerprint checked on restore. A primary/reserve URL alias
references the same stored file instead of retaining duplicate audio bytes.
Unverified rewrites revoke the shared disk mapping. Fingerprints also reject a
file changed by an older cache writer after a rollback.

Telegram IDs are scoped to this bot and a verified public recording. Publishing
an ID requires matching the supplied original file against its stored fingerprint
before tagging/sending. An owner's personal edit cannot reuse or replace that
public ID. Recovery prefers the verified public ID, restores its provenance and
repopulates the VPS cache. The current Bot API recovery helper caps downloads at
20 MiB; direct chat reuse of an existing Telegram ID does not download that file.

## Bounds and cancellation

Resource/product-limit errors do not trigger provider substitution. Chat retains
its existing output budget; app search keeps the existing studio input budget.
Only audio source failures enter the reserve chain. Cooperative operation
cancellation propagates through searches, progress hooks and FFprobe. Cancelled
direct-app recovery waits for its worker to finish before freeing its slot, then
removes the owned temporary output. No new service, paid API or account is required.

## Verification

`test_soundcloud_reserve.py` covers ordering, exact/ambiguous matches, preview
rejection, public/private isolation, shared Telegram IDs, fingerprint tampering,
personal-edit protection, URL aliases, cached fallback searches, direct app audio
versus video, direct SoundCloud preparation and cancellation. Existing voice/chat
SDK tests exercise the common search path. `verify_audio_reserve_live.py` is an
opt-in anonymous live check: an intentionally failed primary must recover a full
public SoundCloud fixture. It does not send Telegram messages or require cookies.

## Search and saved-recording controls

The Mini App main search uses YouTube and SoundCloud as independent primary
sources and offers at most three alternating, relevant choices. Jamendo is the
reserve when both primary searches have no choices, and remains selectable
explicitly. Metadata queries use the existing two search-worker slots; results
are grouped by their actual provider, and duplicate URLs are removed. Explicit
source filters can be switched immediately; repeated queries to one source still
have a per-owner rate limit. Only the chosen recording is downloaded.

A cached chart selection offers the saved recording and new version searches.
The same choice works after an app restart when an owned cached recording in
recent history retains the original chart/catalog identity. Cache availability
is owner-scoped. Choosing a recording while downloading or opening the studio
preserves that action instead of silently switching to playback. Unprepared
SoundCloud recordings sent to chat keep the selected SoundCloud URL, without a
YouTube lookup.

Direct SoundCloud links are fetched from SoundCloud with no YouTube cookies.
If a direct recording cannot be fetched and its public oEmbed metadata is
available, chat offers the original song on the other primary; the app searches
both primaries, excluding the failed canonical SoundCloud URL. The app labels
DRM-protected source errors and never removes the protection. Direct YouTube
AUDIO links first retain exact cache/reserve recovery, then can offer independent
SoundCloud search using a public oEmbed label. YouTube VIDEO links never enter
that audio replacement flow. Missing public metadata can still leave a source
failure. TikTok and Instagram continue to use their own extractors.

Recording menus and source-specific searches also show at most three choices.
Unrequested remix/cover/slowed/live/acoustic/instrumental and similar labels are
filtered; explicit search words (including common Russian/English equivalents)
allow those versions. Relevant official audio precedes a music video with
additional intro/outro. Ranking preserves provider order otherwise; it does not
claim an independent global popularity chart or prove download availability.
