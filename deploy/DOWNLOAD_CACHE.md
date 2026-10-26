# Persistent download reuse

Set `DOWNLOAD_CACHE_DIR=/app/data/download-cache` on the persistent data volume.
`DOWNLOAD_CACHE_BYTES` defaults to 21474836480 (20 GiB). Without a configured
directory the feature is disabled. No additional service or subscription is needed.

Successful chat MP3 downloads and Mini App imports populate a private per-user cache.
Audio is keyed by exact recording; YouTube tracking parameters are ignored. Video
quality and chat/app rendering profiles have separate keys. Uploads, effects and
user-supplied signed download URLs are never shared between users.

Oldest-used files are evicted on insertion to stay within the configured media
budget. Entries unused for 30 days are not served and are removed on subsequent
insertions. SQLite metadata and a temporary atomic write need small additional
space. This is a cache, not a permanent music library or a YouTube access solution.

After successful MP3 delivery, the bot stores its Telegram file_id, scoped to the
same bot and private chat. Subsequent listen/queue/direct audio requests can resend
that exact file without downloading it again, even after filesystem eviction.
Invalid Telegram identifiers are discarded and normal file delivery is attempted.
Studio editing and Mini App playback require actual audio bytes; file_id alone
does not provide a browser playback URL. Mini App "send to chat" also records IDs.

No cookies, provider media URLs, Telegram tokens or passwords enter this index.
The private runtime index contains Telegram file identifiers and must never be
published in Git or source archives. Existing historic downloads are not
automatically indexed. The feature starts accumulating successful new downloads.
