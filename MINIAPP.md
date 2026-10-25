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


## App player and studio upgrade (2026-10-24)

The chat bot code and native command menu are unchanged. The app now provides an explicit play-next queue (up to 100 entries), reordering/removal, listening history for Previous, and per-account browser storage for the queue and last listening position. Resume is a user action, never automatic playback. Device-local files cannot be restored after closing the app; saved files can. Browser storage belongs to the app origin, so a rotated temporary tunnel address starts a new local session.

Studio includes Original/Warm/Night drive/Bright recipes, bass and high-shelf clarity controls, original/effects comparison, trim start/end in seconds, smooth fade-in/out and Save mix to library. WAV rendering is local; Save explicitly uploads the resulting file in authenticated mode. Demo keeps the result only in memory. Existing limits remain: source and exported mix up to 3 minutes, uploads up to 20 MiB. Speed changes pitch. Trim and fades are applied to Preview/export/saved mixes; live full-track listening applies tone/speed only.


## MP3, longer tracks and voice search (2026-10-24)

Authenticated Mini App studio now uses its own FFmpeg endpoint on the existing host, not chat messages. Select MP3 (192 kbps) or WAV, trim, fades, bass, treble, independent tempo/pitch (-6 to +6 semitones), reverb, echo, lo-fi, loudness normalization or compression. Preview renders a short selected segment; full export supports source and result up to 30 minutes. Input limit 49 MiB; WAV output limit 96 MiB; durable library uploads retain their existing 20 MiB limit. Demo remains local WAV with the existing three-minute browser memory bound. New server-only options require Telegram sign-in.

Audio upload/FFmpeg output live only in a temporary folder until the response finishes, then are deleted. The studio/voice worker admits one request at a time, uses bounded child processes with timeouts, and rejects arbitrary expressions, unsupported demuxers and external protocols. Normal bot code and chat UI are unchanged. No API subscription.

Search includes an optional microphone recording or uploaded audio clip (<=30s, <=8 MiB). The user explicitly submits it for word transcription, reviews/edits the resulting query, then presses Search. This searches spoken titles/artists or recognizable sung lyrics, not melody-only humming or a Shazam fingerprint database. Microphone access needs HTTPS and the user's browser permission; file upload is the fallback if a Telegram WebView does not expose recording.

The official open-source multilingual Whisper base model runs on CPU in an isolated short-lived subprocess, at most two Torch threads; raw recordings are removed after transcription. Install base weights in the existing model-cache volume before enabling on a new machine (`python -c "import whisper; whisper.load_model('base')"` as the bot container user). The official downloader verifies SHA256. This machine's base.pt was installed and hash verified; no token or paid API is used. Model weights are not included in the portable source archive.


## Effect chain and queue recovery refinement

Studio now exposes twelve selectable effects (including delay, presence EQ, mastering, wide reverb, high/low-pass and reverse), up to eight in selection order. Apply to full track plays the actual processed output inside the app; preview is optional. The Original/Effects comparison reuses the last processed audio for the same settings, without another server request. Changing settings invalidates old output. Export and Save always use selected effects, even while auditioning the original. New cyan/amber colors and a local SVG sound-lab illustration have no external image dependencies.

Preparation starts with Checking recording rather than claiming a worker queue before the server answers. Actual download queue wait is capped at30s; download timeout240s is shown immediately while cooperative worker cleanup retains capacity. Queued cancellation finishes immediately. Requests and browser polling have bounded deadlines and RU/EN failure explanations. These changes do not guarantee an external music source will provide every recording.


## Mobile download, live audition and lyrics refinement

Studio export now requests a temporary HTTPS file ticket instead of trying to download a browser blob URL inside mobile Telegram. Telegram8+ uses its native downloadFile popup; the file-ready dialog also offers a user-gesture Download button and Open file fallback. On iPhone the opened file can be shared/saved to Files. Export tickets last10minutes, use random32-character bearer tokens, are owner-control checked, support GET/HEAD/Range via FileResponse, and never expose local paths or permanent public library links. The separate temporary export cache is capped at256MiB,128entries and10minutes; these are not durable library saves. Closing/restarting the bot invalidates outstanding tickets. No success message claims the file has been saved to the phone.

Duration metadata is refreshed after loadedmetadata; server preview derives its end from the probed source rather than relying on a mobile browser's early duration value. Source and output limits are unchanged.

Native Web Audio now auditions reverb/wide reverb, echo/delay, lo-fi, compression, presence EQ and high/low-pass filters while the track continues playing, with no model, network call or full-track browser decoding. Reverse, integrated loudness/mastering and independent pitch still use Apply to full track. Live audition approximates FFmpeg's final effect algorithms; use Apply to hear the exact exported result. Processed audio bypasses the live graph to avoid applying effects twice. Tone uses familiar Lower/higher sound wording.

Lyrics is available in track actions and full player through LRCLIB's free public read API. Only selected song title/artist metadata is sent, never audio, Telegram IDs or credentials. The server uses a named User-Agent, serializes requests, caches up to128public responses for1hour, honors Retry-After, bounds provider payloads and escaped text. Multiple matches require selection. Coverage is not guaranteed.

User explicitly deferred new AI systems/paid recognition/hosting. No new AI model, paid API or humming recognition was installed in this refinement. Existing local word transcription remains. Real iPhone Telegram native UI needs user confirmation; isolated Chromium and WebKit cover app code and mocked native download calls, not an actual phone OS download.


## Link imports and phone controls

Search now has Music / From a link tabs and a Home shortcut. Direct public YouTube, SoundCloud(audio), TikTok and Instagram links can prepare audio MP3 or video MP4. Apple Music/Yandex Music/Spotify links resolve public metadata and open recording search; they do not extract subscription originals. Video uses H264/AAC MP4, faststart and a generated preview frame; aspect ratio is preserved. Silent videos do not show audio-extraction action. Audio from cached video uses the existing private temporary file, not another provider download. Audio can be opened in Studio and explicitly saved to the library.

Public source restrictions and availability still apply. No guarantee of downloading every link. Inputs are classified against known providers, credentials/nonstandard ports/arbitrary hosts are rejected, one link worker is admitted, source/output <=49MiB and duration<=30min. Downloads/transcodes run in bounded child-process groups; cancellation kills the owner's worker and cleans temporary files. Long app-only operations do not hold the chat/library mutation lock, so browsing the library remains responsive. No chat message/session mutation. Temporary native file tickets/cache retain the existing10min/256MiB limits; no permanent video library storage was added.

Studio restores separate Speed/Tone labels, large minus/plus buttons, speed and tone presets and larger touch targets. Tone changes independently from tempo in the final mix. Reverb/echo strength(0-100%) applies to the room/wide reverb/echo/delay group in live audition and FFmpeg export. Repeated control changes no longer rebuild an unchanged live graph. Normal chat bot source is unchanged; no paid service or new model installed.


2026-10-24 LARGE MEDIA / PARAMETRIC STUDIO (supersedes earlier limits):
Mini App only; normal bot unchanged. Limits: source/media256MiB,2h; rendered WAV/MP3 output512MiB; ephemeral cache1GiB with duration-aware expiry. Duplicate concatenated YouTube URLs normalized. Actual user video7DVM7DYJX1c downloaded791sec/87.3MiB in22.7sec,720pMP4. Public Vimeo/Bandcamp single-track support added. Catalog Spotify/Apple/Yandex links resolve metadata and search matching recordings, not subscription originals. Provider availability/login/region can still prevent downloads. Local uploads through temporary tunnel may meet gateway body limits.
Studio: linked varispeed or independent speed/pitch,15 effects/up8 simultaneous. Adjustable5bandEQ,compressor,cutoffs,delay/feedback,room,stereo,tremolo,saturation. Live audition approximate; Apply renders exact FFmpeg chain. Background owner-scoped render jobs avoid long HTTP response; cached source tickets avoid phone re-upload; Save persists server result directly. Native MP3/WAV tickets retained. No purchases/new AI.
212 offline tests passed; isolated Chromium+WebKit UI passed including linked controls,JSON cached source,parameter settings,native download; actual physical iPhone not observed. Current tunnel reachable with normal DNS, no workaround installed. New modules app_limits.py/app_dsp.py/app_render_jobs.py. Deployment current; final speed label multiplier corrected. Backup follows.


2026-10-24 INDEPENDENT TONE / SIMPLER STUDIO:
User says linked works, separate tone inaudible. Cause: independent pitch was server-render-only and slider did not trigger processing. Now release/change or tone step schedules debounced full server Apply automatically, retains playback position, skips stale/foreign-track/navigation work and waits existing job. Still not instant realtime pitch; displays processing. Demo independent pitch still requires Telegram server. Switching linked->separate with nonzero pitch also schedules render. Speed slider now uses same linked pitch sync as presets (fixed inconsistency).
Studio reorganized into6 common effects plus expandable other effects. All15 remain; selected advanced effects stay expanded. Friendly RU/EN names, Gentle/Balanced/Strong parameter presets for12 tunable effects, advanced sliders remain optional, reset effect parameters button. No normal bot changes, no purchases.
Verification:15 studio tests passed including independent+12semitones actual440->880Hz without duration change; UI Chromium/WebKit regression includes automatic separate tone request, processed playback rate1, easy effect preset controls. Final UI run result to verify before deployment. Session backup follows.


2026-10-25 VISUAL REFRESH / DISCOVERY:
User wants professional Mini App UI inspired by music apps, animations, simpler flows, no paid hosting yet; current laptop workflow preserved. Original design implemented directly in app.js/app.css, no copied template/assets/dependencies: violet/mint theme, original CSS vinyl and mood artwork, restyled album cards/player/studio/search/dialogs, navigation entry animation, playback-only vinyl/studio wave animation, reduced-motion override. Four mood entry points invoke existing search (not charts/AI/community recommendations), RU/EN, demo searches original samples. Existing persisted resume card reused; duplicate new card removed after visual QA. Existing6common/advanced effect organization preserved, normal bot untouched.
Research for NEXT phase only: Swing Music open-source UI inspiration https://github.com/swingmx/swingmusic (AGPL; no code copied); ListenBrainz open listening data https://listenbrainz.org/data/ and statistics docs https://listenbrainz.readthedocs.io/en/latest/users/api/statistics.html . No third-party chart scraping/integration or public sharing of users' playlists added. Proposed next: attributed ListenBrainz discovery with cache and explicit opt-in shared playlists; optional name-that-track game from own library. These are proposals, NOT implemented. No paidAPI/new AI/server purchase.
QA includes four mood cards ->actual demo search, reduced-motion, existing playback/studio/links/lyrics/native download tests; final run needs verification. Source and full runtime backup follow.


2026-10-25 PHONE PLAYER / TONE LOAD CORRECTION:
User reports tone lag, poor mood searches, phone player compressed; likes current visual style. Removed four mood/discovery shortcuts entirely; no replacement chart claim. Root cause found in frontend: independent tone auto-rendered FULL track per change. Now debounced independent tone audition requests preview=True (15sec bounded server plan), MP3, source offset=current original position; full Apply/export remain explicit and full-length. Latest settings stale-result guard preserved, one active render; automatic preview not put in full-mix A/B cache. Streamed ticket and legacy Blob playback both supported. Source position tracked across preview invalidation; linked tone step/slider resumes playing original when invalidating old processed source. This is still server short-preview, NOT realtime independent pitch. RU/EN explanation says15sec thenApply/Download forwholetrack. No external AI needed/installed.
Mobile player redesigned as2rows: full-width44pxcover/title/artist/favorite thentransport+seek+times;116pxheight reserved above62pxsafearea navigation. Increased mobile metadata/search result typography, minmax0 grids and narrow-screen padding/source layouts. Existingdesktopstylepreserved. Chromium+WebKit UI PASS, regression asserts no moodcards, auto tone preview=True, original speed unchanged, native MP3/WAV existing flows. Width320/360/390/430/540/720 verifies no pageoverflow, titlewidth>=120, all playercontrolswithinviewport. Physical phone not observed. No normalbot/backend/paidservicechange.
Latest source publish/deploy and backup follow.


2026-10-25 SOCIAL LINK FORMAT FIX / LIVE PLATFORM MATRIX:
User says TikTok link works normal bot but fails Mini App; asks all platforms. User authorized arbitrary public examples. Reproduced before fix on real TikTok6742501081818877190 and InstagramChunk8-jurw: Requested format is not available. Root: MiniApp appliedYouTube360/720height/codec selector to social combined streams; workingchat uses b[ext=mp4]/b plusdesktopUA. App-only fix matches social videoformat andUA; cookiesremainNone, boundedlimits/phoneFFmpegnormalization unchanged. Normalbotuntouched. Regression exercises realyt_dlpformatselector against1080combined-onlyMP4 forTikTokdirect/short/Instagram atrequested360.21media+catalogtestsPASS.
Deployedfix. Isolated real API TestClient usescurrentDocker code andactualinternet, syntheticfixturetoken/UID, temporaryDB/caches cleaned. POST/api/linkTikTok200videoMP4,Instagram200videoMP4,SoundCloud200audioMP3,YouTubevideo200MP4,YouTubeaudio200MP3; allnativeGET Range206/32bytes. Spotify/Yandex/Apple validlinks200kindsearch/querynonempty. Source restrictions canstillaffectother/private/removedvideos; this isverifiedpublicexamples,notallpossibleURLs. InitialguessedAppleIDinvalid; replacedvalidShapeofYou1193701392passed. Catalogmatchingfullpreparation followup running; verifyresult beforeclaim. No purchases/proxies/securitychanges/externalAI.

Followup live catalog pipeline PASS all3: Spotify->5searchchoices->EdSheeranShapeofYou->readyMP3Range206; Yandex2303525/20220545->5choices->Vkrayumagnoliy->readyMP3Range206; AppleShapeofYou1193701392->5choices->EdSheeranShapeofYou->readyMP3Range206. Uses real /api/search,/api/prepare,/api/jobs,/api/audio with app-only downloader in isolated temporary TestClient, not mocked providers. Native publicHTTPSphone not manuallyobserved; currenttunnelhealthy. Finalsourcepublish/backupfollows.


2026-10-25 update: short TikTok links now explicitly enable yt-dlp's vm.tiktok extractor; direct TikTok and short-link extractors have different names. Real short-link MP4 (360/720/1080/original) and MP3 API checks passed with byte-range downloads. Added a registration regression.
Link imports no longer default to a 2-hour/256-MiB product cap. MINIAPP_LINK_MAX_BYTES and MINIAPP_LINK_MAX_SECONDS default to0 (disabled). Free temporary storage still bounds operations, with512MiB reserve and space for source, conversion and delivery. Live broadcasts and platform login/access requirements remain separate. Studio processing and permanent-library quotas are unchanged. Operational request/transcoding timeouts remain. Temporary delivery supports one file above its usual cache target with space-aware copying and managed-cache eviction.
Video choices:144p,240p,360p,480p,720p,1080p,Original. Requested output is reduced when needed, never upscaled. Removed the old public-recordings/size/duration advertisement.215 offline tests, updated extractor regression, and Chromium/WebKit UI checks passed. No new paid service.
