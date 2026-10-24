# SwiDJ Mini App — local first release

The Telegram bot remains the main app. This optional web UI adds Home, Search,
Your music and Studio without replacing chat commands or requiring a paid API.

## Try it locally

The local Docker Compose configuration enables the server in the bot process,
and publishes it **only on the laptop's loopback interface**:

```powershell
docker compose -p swidj-local -f compose.local.yaml up --build -d
```

Open **http://127.0.0.1:8765** in a browser. Outside Telegram this is explicitly
a demo with six original synthesised instrumental loops. Demo playlists and
favorites stay in browser storage; real user libraries are never shown there.

For a demo without the bot or any credentials:

```sh
pip install -r requirements-miniapp.txt
python miniapp_server.py --demo
```

## What works

- Responsive desktop sidebar and mobile bottom navigation, persistent player,
  seeking, volume, next/previous track, repeat and RU/EN UI.
- Demo search, favorites and playlists. In Telegram, signed authentication
  connects these screens to the bot's existing SQLite library and live state.
- Real search uses the recording finder. Selecting a track prepares its full
  recording and plays it **inside the app**. Catalog entries with ambiguous
  recordings offer choices inside the app. No automatic chat messages or chat
  navigation are part of searching, preparing, playing or downloading audio.
- Audio preparation has visible queued/loading states, cancellation and retry.
  There are at most two workers, one pending task per user and eight pending
  tasks globally. The app has separate recent listening history and temporary
  audio cache, bounded to 256 MiB / 24h; it does not replace chat studio state.
  External recordings may fail or become unavailable; subscription-catalog
  protected originals are not promised.
- Download buttons save audio to the device. Compatible Telegram clients use
  native file download with a private, scoped link valid for two minutes;
  other browsers use a local Blob download. “Send to chat” is a separate,
  explicit action and never opens the chat automatically.
- Your own audio can be saved from Studio without sending it to the bot chat.
  Uploads require verified Telegram identity and valid audio, up to 20 MiB and
  one hour. ffprobe is restricted to local-file/pipe protocols. At most two
  uploads are processed at once. Durable audio storage is capped at 128 MiB per
  user and 512 MiB total; duplicate app uploads are deduplicated per user.
  Unfavoriting preserves the app library entry. Permanently deleting a file
  uploaded in the app requires explicit confirmation and reclaims its owned
  server copy after committing library/history changes. General bot recordings
  are not physically purged by this action.
- Browser Studio opens a local file (up to 20 MiB), plays adjustable bass and
  speed, previews up to 15 seconds, and exports WAV. Source audio and the full
  exported mix must each be up to 3 minutes to bound browser memory. Speed also
  changes pitch. Processing stays on the device; a file uploads only when the
  user explicitly chooses Save. The bot retains full-track MP3 tools.
- Playlist creation, renaming, adding/removing tracks, confirmed playlist
  deletion, favorites, and confirmed library removal. Deleting a playlist or
  membership keeps its tracks in the library. Playlist playback follows its order.
  General removal updates memberships. App-owned uploads use the separate
  permanent file-deletion confirmation described above.
- A full player opens from the bottom artwork/title. Library state refreshes
  when the app regains visibility. Failed database commits preserve live state;
  stale/concurrent browser renders cannot overwrite a newly selected track.

## Connect inside Telegram later

Production hosting has **not been deployed**. For free Telegram testing, run
`python miniapp_tunnel.py start` (Windows: `Start SwiDJ App.cmd`). This explicitly
starts the official Cloudflare Quick Tunnel container, checks the public URL,
updates private `MINIAPP_URL`, and restarts the bot. The normal native command
menu stays available; `/app` and a separate home-menu button open the app.
No Cloudflare account, paid API, custom domain or inbound firewall port is needed.
A Quick Tunnel registration may expire even while its container is running. Run the Start helper again to recreate an unreachable registration, then open a fresh `/app` button. The URL changes when the tunnel is recreated and works only while the laptop,
Docker, bot and tunnel are running. Quick Tunnels are for development/testing.

`python miniapp_tunnel.py status` checks the current address.
`python miniapp_tunnel.py stop` (Windows: `Stop SwiDJ App.cmd`) closes public
access while leaving the normal bot running. Run tunnel controls only as its owner.
The normal bot Stop action stops the application; the tunnel may stay running
until separately stopped, but cannot serve the stopped app.

For a permanent launch, provide a stable HTTPS origin and set `MINIAPP_URL`
privately. Do not publish .env or the token. A real Telegram WebView test with
your account is required before claiming end-to-end phone compatibility.

`MINIAPP_ENABLED=true` enables the server. `MINIAPP_HOST=0.0.0.0` is appropriate
inside Docker with a loopback port mapping; outside Docker default to 127.0.0.1.
Default port: 8765. An HTTPS reverse proxy and deployment resource selection are
a separate step. Keep private credentials out of the frontend and repository.

## Security and validation

API calls require Telegram initData with a checked HMAC, auth age <= 1 hour,
strict numeric identity and no duplicate fields. The client cannot select its
user ID, submit a media URL, or request an arbitrary filesystem path. API calls
share the bot's per-user lock. Owner maintenance/blocks and search/download
controls apply. No permissive CORS, private URLs, tokens or paths in responses.
The API is read-only without authenticated initData; demo assets are public.

Run backend tests using the normal offline suite. Isolated Chromium checks:

```sh
docker build -f scripts/Dockerfile.miniapp-qa -t swidj:miniapp-qa .
docker run --rm --network none -v "$PWD:/workspace:ro" -v "$PWD/qa-output:/out" swidj:miniapp-qa
```

The QA browser has no access to desktop profiles, accounts, private credentials,
or the Internet. It tests playback, preview/WAV, search, playlists, favorites,
languages, untrusted titles and mobile layout. It does not prove Telegram
WebView compatibility on every phone; a real HTTPS Telegram session is still
needed before a public launch. There are no social feed, payments, public sharing,
cloud storage promises, or paid recognition integrations in this release.
