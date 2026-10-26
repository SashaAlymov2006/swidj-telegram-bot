# Source recovery

The normal source remains first. Existing per-user disk cache and private-chat
Telegram file_id reuse remain enabled. Cached search results for the exact query
are retained for up to seven days (300 entries) and used only after a search error.
No source error is converted into a fabricated successful download.

When an audio source fails, the app/chat can retrieve that same user's previously
delivered recording using the official Telegram getFile API. The standard API's
20 MB download limit applies to this recovery path; chat file_id resending does
not require downloading the file to the VPS. Partial transfers are discarded,
tokens never enter public URLs, and users cannot read each other's identifiers.

## Optional Jamendo reserve

Register a read-only non-commercial developer application and set
`JAMENDO_CLIENT_ID` privately in the server environment. A client secret or Google
account is not required. Do not commit the real ID or private environment file.

Jamendo is queried after an upstream search error and no saved search result.
Results remain explicit choices with Jamendo credits. When a selected recording
fails, automatic matching requires one unique exact normalized artist/title,
matching version words, and duration within two seconds. This is conservative
metadata matching, not proof of audio identity. Ambiguous matches are rejected.
Previously nonexistent tracks do not become available merely by enabling Jamendo.

Only `audiodownload_allowed=true` tracks with CC BY 3.0/4.0 or CC0 are admitted.
Permission is rechecked before download. No-derivatives, noncommercial-only and
share-alike recordings are excluded from this integration. Source/license links
are shown in the app and Telegram delivery. Jamendo files are not mirrored into
the 20 GiB persistent source cache; transient app preparation is used for playback
and processing. There is no bulk backup of the Jamendo catalog.

Public Jamendo track links also work in Mini App link import. TikTok/Instagram
retain their direct extractors and do not depend on YouTube. A fallback audio
recording cannot replace a requested video.

API conditions and quotas: https://developer.jamendo.com/v3.0
Download permission: https://developer.jamendo.com/v3.0/tracks/file
Terms: https://devportal.jamendo.com/api_terms_of_use

Source outages, missing catalog entries and human account verification can still
require intervention. No permanent availability or universal catalog is promised.
