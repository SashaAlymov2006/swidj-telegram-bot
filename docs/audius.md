# Optional Audius source

Audius is an independent reserve for bot and Mini App searches, version choices,
charts and single-track links. No extra server or listener account is required.
Existing YouTube/SoundCloud behavior remains available. Automatic exact-match
recovery tries SoundCloud, Audius, then Jamendo after the normal cache/Telegram
and primary-source paths. Ambiguous title/artist/duration matches are rejected.

## Free API setup

1. Log in at https://api.audius.co/plans and create a key on the Free plan.
2. Set `AUDIUS_API_KEY` and `AUDIUS_BEARER_TOKEN` in the private backend `.env`.
   `AUDIUS_ENABLED=false` disables the source. Recreate the bot container after
   changing environment values. Never put the bearer token in frontend code,
   Git, public archives or logs.
3. Verify a permitted full recording from the deployed host before relying on
   the source. Provider buttons appear only for checked results.

The documented Free tier offers 10 requests/second and 500,000 requests/month;
verify current limits with Audius. This integration never upgrades a plan.
Requests are paced locally, responses bounded, and `Retry-After` respected.

## Availability and files

Only tracks marked `is_downloadable=true`, public, ungated and accessible are
eligible. Search uses `has_downloads=true` and still validates returned fields.
Stream-only, unlisted, gated and denied recordings are excluded. The complete
MP3 is retrieved through the documented stream endpoint **after** checking
download permission; the original-download endpoint can return large WAV files.
Audio is validated with ffprobe against expected duration before retention.

Metadata requests go to the fixed Audius API. Bearer headers and API-key query
parameters are not forwarded to redirected storage nodes. Media redirects are
bounded, HTTPS-only, and checked against private/local network addresses. Normal
file budgets, cancellation, per-user cache isolation and public fingerprints
apply. Audius attribution links are retained in the app and Telegram cards.

This is an additional catalog, not a guarantee of all popular original songs.
Source availability and author permissions can change after a preflight.

References: [Audius SDK and plans](https://docs.audius.co/sdk/),
[track API documentation](https://docs.audius.co/sdk/tracks/).
