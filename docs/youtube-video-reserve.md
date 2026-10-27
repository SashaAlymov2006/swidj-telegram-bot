# External YouTube video reserve

The normal downloader and existing cache run first. If YouTube video extraction fails,
an optional jaky.dev adapter can fetch the requested video using its own infrastructure.
It is shared by chat and Mini App. Audio downloads, search, other platforms and the
studio are unchanged. This is an independent provider, not an official YouTube service.

Configure backend-only `JAKY_API_KEY` and `YOUTUBE_VIDEO_RESERVE_ENABLED=true`.
Never place the key in the Mini App, repository, logs or recovery archives. No browser
cookies or YouTube account credentials are sent to the provider. Disable the flag to
return immediately to the existing downloader without the reserve.

Supported reserve requests: 360p, 480p, 720p; automatic quality selects 720p. When a 1080p request needs the reserve, it uses 720p and displays only
"Available up to 720p" (Russian: "Доступно максимум 720p"). The app hides the
1080p option for that prepared result. No provider or failure explanation is displayed.
Native lower-resolution sources retain their dimensions. Existing chat file limits
and Mini App disk budgets remain in force.

The provider advertises 100 free requests/day. SwiDJ allows up to 90 attempts/day,
shared through `video_reserve.sqlite3` alongside the state database, reset at 00:00
Asia/Jakarta. Calls made outside SwiDJ still consume the provider quota. There is one
reserve request at a time, no paid upgrade, no quota bypass, no unbounded retries.
429 pauses the reserve for an hour; other failures pause it for a minute. Persistent
cache hits do not spend another provider request.

Only two observed HTTPS media hosts are accepted (`dl1.ezsrv.net`, `dl2.ezsrv.net`).
Each redirect is checked; credentials go only to the fixed API host. Downloads have
byte/time limits, cancellation checkpoints, temporary-file cleanup and ffprobe checks
for H264 video, AAC audio, valid duration and requested resolution. The provider is
trusted to return the requested video; this is not cryptographic identity verification.

On 2026-10-27 VPS trials verified full files of 19.06 seconds, 174.22 seconds at 720p,
and 634.62 seconds at 360p. One initial API extraction took about 29 seconds; warmed
full transfers took 1.7-2.8 seconds. These observations are not a speed/uptime guarantee.
WebDownloader also delivered a full 174-second 720p file in 77 seconds, but other
requests timed out; it is not connected to production.

Provider documentation: https://api.jaky.dev/playground/download/youtube
Free tier: https://api.jaky.dev/
