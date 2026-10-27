# Recording availability

Bot and Mini App search results are checked before presenting recording choices.
The bounded preflight checks an owned/public cache entry or extracts a source's
audio URL and reads a small media sample. Protected recordings, previews,
unexpected hosts, invalid durations and unreadable streams are omitted.

Up to three suitable recordings are offered. YouTube, SoundCloud and permitted
Jamendo tracks are checked independently. This is not a full download or a
guarantee that the source will remain available afterwards. Positive checks are
cached for three minutes; failed checks for twenty seconds. Source credentials
are not forwarded to other providers.

Existing messages retain their old buttons; repeat the search to get a newly
checked list. Source failures can leave fewer results, including an empty list.

Provider buttons are also checked for the current query. Bot version menus,
Mini App recording dialogs, chart choices and search filters omit providers
without checked recordings. Before a first search, all search filters remain
available. A provider's reserve results do not count as availability of that
provider. Checked query results are reused for up to sixty seconds, with empty
results cached for twenty seconds and separated by owner and catalog query.

## Search and preparation performance

YouTube preflight uses yt-dlp's actual downloader in test mode (normally about
10 KiB, with a 64 KiB guard and temporary-file cleanup). This exercises the same
download path instead of rejecting a track from a raw extracted URL alone.
It still cannot guarantee the rest of a file or future source availability.

Candidate checks run in pairs with a global limit of two active remote checks;
ranking and cancellation context are preserved. The combined search checks up
to two choices per primary provider for its compact three-item list. Inventory
checks stop after one working recording; opening a provider expands choices.
Raw search metadata is cached for sixty seconds (twenty for empty searches),
bounded to 128 owner/query/provider entries. Short-lived app result snapshots
allow immediate repeated requests without another source lookup, refresh owned
playability, and remain owner-scoped (256 entries, fifteen seconds positive,
five empty). New uncached requests retain the existing rate limit.

Already encoded MP3 imports are remuxed without another lossy encode after
validation. Other formats are still converted to MP3, and applying studio
effects still renders audio normally.

The 20 GiB persistent download-cache ceiling remains unchanged: observed use
was about 293 MB, so increasing the ceiling would not improve present latency.
