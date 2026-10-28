# SwiDJ Visual Studio

An optional, isolated music-video editor. The normal bot and audio studio do not
depend on its renderer. No Telegram polling or library writes happen here.

## Features

- Audio from the existing studio, including its applied mix, or an uploaded file.
- Image, silent video, or gradient background; optional central image/logo.
- Circle, triangle, square or no central shape; ring, bars, wave or no spectrum.
- Eight presets, particles, glow, colors, motion, text and response controls.
- MP4 H.264/AAC, 720p/1080p, 30/60 fps, landscape/portrait/square.
- Full audio or selected interval. Export settings are immutable per job.
- Owner-scoped history, cancellation, temporary downloads and RU/EN interface.
- Logo/spectrum placement, size and pulse; cover/contain background framing,
  pan, blur, vignette, text color/size/position and audio/video fades.
- Undo/redo, up to twelve named on-device visual styles and validated JSON transfer.
- Automatic draft restoration while its server files remain available; imported
  tracks open a fresh draft. Pending, unuploaded file selections are not restored.
- A five-second 720p30 video sample before exporting the full selected quality.
- Image-only updates reuse the original audio, preview and FFT data. Unchanged
  video backgrounds are reused as well; older drafts remain unchanged.
- Optional synchronized lyrics: the Add lyrics button appears only for a matching
  recording with valid LRC timestamps. Original artist/title/duration are checked;
  tempo and trim are mapped to the exported mix. Reverse audio disables lookup.
  Plain or mismatched lyrics never become a fabricated timed overlay.
- Lyrics highlight the current line during playback/export, with highlight,
  soft highlight and pulse styles, placement/size and timing adjustment. Source
  attribution is retained. The existing ordinary chat lyrics reader is unchanged.

Preview uses a bounded Canvas surface and precomputed audio features; final frames
are rendered in a separate process. Preview and export share scene parameters,
but browser/Pillow fonts and glow are not pixel-identical. This is an audio-reactive
visualizer, not a guaranteed musical beat/transcription model.

## Local development

Use a dedicated Python environment; install `requirements.txt`, then:

```sh
python -m music_video.server --dev
python -m unittest discover -s music_video/tests -q
```

Open `http://127.0.0.1:8792/`. Local mode binds only to loopback and requires a
same-origin request with `X-SwiDJ-Local: 1` for APIs. FFmpeg is required; the local
requirements include a portable fallback. Production uses the system FFmpeg.

## Production

Run `compose.yaml` as a separate Compose project on the bot network. Supply the
existing Telegram token privately through an env file, plus `SWIDJ_NETWORK`.
Never expose the worker port publicly. Route `/music-video/*` through the existing
HTTPS reverse proxy, stripping `/music-video`. The frontend uses relative URLs.

The service validates Telegram initData and checks the existing bot's library
endpoint for access. It never accepts arbitrary remote media URLs. Download URLs
are expiring bearer links: do not share them publicly.

The optional Video tab appears only after a successful worker probe. Its shared
library picker uses the same bot/Mini App collection; the current audio mix is an
explicit separate source. `miniapp/visualizer-bridge.js` and `web/bridge.css` are
served by the worker.
Deployment may override only `/assets/app.js` in the proxy's persistent static
directory, avoiding a main-bot restart. Keep the original proxy configuration and
asset hashes; future main-frontend updates must refresh/remove this override.
Validate Caddy configuration before a graceful reload. Rollback restores the
previous configuration and reloads Caddy; the main bot remains running.

## Resource policy and recovery

One renderer runs at a time. Container limits: 1 CPU, 2 GiB RAM, 64 processes;
workspace budget 12 GiB, upload budget 512 MiB combined, expiry 3 hours after work
finishes. These protect the existing service; full-length 1080p60 exports can take
substantial time. A device's preview FPS is independent of export FPS.

Jobs survive editor closure. Finished results remain in “My videos” until expiry.
Service restart preserves finished jobs; unfinished jobs are marked interrupted.
Uploaded source images/audio and temporary videos expire automatically. Custom
presets are stored per user in the device's browser storage, not in the bot DB.

Real iPhone/Android and browser interaction must be checked separately from Python
pipeline tests. Do not claim physical-device validation from API/render tests.

The Deno tests exercise actual editor code against a minimal DOM contract, plus
scene state and navigation. They are not browser emulation or physical-device QA:

```sh
deno test --no-config --allow-read=music_video,miniapp/app.js music_video/tests/state_test.js music_video/tests/editor_flow_test.js music_video/tests/navigation_test.js music_video/tests/timing_test.js music_video/tests/player_lyrics_test.js
```

## Optional lyrics in the ordinary player

Open the expanded player, then Lyrics. Read displays the complete available text;
With music appears when LRCLIB has timed lyrics matching the recording's title,
artist and duration. Switching modes does not restart playback. Tap a timed line
to seek, or adjust its delay. Closing lyrics leaves the music playing. Unsynced
lyrics still work if timed lookup is unavailable. No guessed timing or paid AI
transcription is used. Processed previews map back to the original source clock;
reverse playback uses reading only. The existing chat lyrics remain unchanged.

The video editor now has twelve presets, including Vinyl, Neon Tunnel, Aurora
and Neon Grid, plus a mirrored spectrum and optional rotating cover. These use
the existing Canvas preview and isolated Pillow/FFmpeg worker. Old scene defaults
and the main bot's resource allocation are preserved.
