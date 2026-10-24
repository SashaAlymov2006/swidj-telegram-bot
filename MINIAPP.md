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
- Real search uses the bot's YouTube recording finder. “Get it in the bot” sends
  a selection to the user's private chat and reuses the existing download,
  retry and track-card flow. It does not promise subscription-catalog originals.
- Local playback is available for owned saved audio and the current downloaded
  track. Other saved catalog entries offer the chat download flow.
- Browser Studio opens a local file (up to 20 MiB), plays adjustable bass and
  speed, previews up to 15 seconds, and exports WAV. Source audio and the full
  exported mix must each be up to 3 minutes to bound browser memory. Speed also
  changes pitch. Files are not uploaded. The bot retains full-track MP3 tools.
- Playlist creation, renaming, adding/removing tracks, confirmed playlist
  deletion, favorites, and confirmed library removal. Deleting a playlist or
  membership keeps its tracks in the library. Playlist playback follows its order.
  Removal updates memberships, not physical audio files. No automatic permanent
  file purge was added.
- A full player opens from the bottom artwork/title. Library state refreshes
  when the app regains visibility. Failed database commits preserve live state;
  stale/concurrent browser renders cannot overwrite a newly selected track.

## Connect inside Telegram later

Production hosting has **not been deployed**. For free Telegram testing, run
`python miniapp_tunnel.py start` (Windows: `Start SwiDJ App.cmd`). This explicitly
starts the official Cloudflare Quick Tunnel container, checks the public URL,
updates private `MINIAPP_URL`, and restarts the bot. The native composer menu
button reads **SwiDJ**; `/app` and the home menu also offer a Web App button.
No Cloudflare account, paid API, custom domain or inbound firewall port is needed.
The URL changes when the tunnel is recreated and works only while the laptop,
Docker, bot and tunnel are running. Quick Tunnels are for development/testing.

`python miniapp_tunnel.py status` checks the current address.
`python miniapp_tunnel.py stop` (Windows: `Stop SwiDJ App.cmd`) closes public
access and restores the normal bot menu while leaving the bot running. These
actions change the bot's configured menu for everyone; run them only as its owner.
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
