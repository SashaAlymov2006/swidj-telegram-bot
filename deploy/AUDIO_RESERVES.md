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
