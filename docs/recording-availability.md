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
