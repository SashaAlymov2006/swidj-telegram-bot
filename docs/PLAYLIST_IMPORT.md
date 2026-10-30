# Playlist import

Mini App: **My music → Import playlist**. Paste a public collection URL or one `Artist — Title` per line, preview the accessible tracks, then confirm. Bot: send a playlist URL, use the import button under playlists, or send `/import` followed by a list in the same message.

Imports create ordinary shared SwiDJ collections. Audio is not downloaded in bulk. Opening a track runs the existing recording-selection pipeline across available sources; the user chooses a version before preparing audio. Catalog metadata is not a protected subscription-service audio download. Unavailable entries remain a source availability limitation; when the provider reports a larger total, the preview shows accessible/total counts.

Adapters: YouTube/YouTube Music public playlist URLs, SoundCloud sets, Spotify public playlist/album embeds, Apple Music public playlists and album metadata, Deezer public playlists/albums, Bandcamp album metadata, Audius public playlists/albums and Jamendo public lists. Yandex public playlist/album parsing is conditional: current VPS probes are region/access blocked, so it must not be advertised as verified link import. A pasted track list works independently of the source catalog, including exported lists from Yandex, VK or other services.

No remote playlists are modified. This is a saved copy, not automatic synchronization. Private lists require access not supplied by this feature. Spotify embed pages can expose only a public subset; do not assume completeness where the provider does not publish a total. Audio availability and recording identity still depend on the existing source checks.

Imported lists accept up to 500 unique entries, 30 collections per user, and 50,000 text characters. Existing regular collection/favourites limits are unchanged. Imported collections can be edited up to the import limit. Duplicate identical imports reuse the existing collection; different lists never overwrite an edited list. Drafts are per-user, expire after 30 minutes and require explicit confirmation. The API checks Telegram signatures and ownership, serializes per-user writes, bounds metadata concurrency and preview requests, and uses the existing atomic SQLite library transaction. There is no schema migration.

Single YouTube watch URLs that happen to contain a `list` query still follow the existing single-video flow; import uses `/playlist?list=...`. TikTok and Instagram remain individual-publication audio/video features, not music-playlist catalogs.

Provider references: [Audius API](https://docs.audius.co/api/), [Jamendo playlist tracks](https://developer.jamendo.com/v3.0/playlists/tracks), [Spotify playlist API](https://developer.spotify.com/documentation/web-api/reference/get-playlists-items). No new paid API, account login or remote-account modification was introduced.
