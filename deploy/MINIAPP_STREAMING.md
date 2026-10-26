# Mini App playback and phone inputs

Prepared tracks play through native same-origin HTTP streaming rather than
waiting for a complete authenticated fetch/blob transfer. The browser can request
byte ranges for startup and seeking. Studio processing continues to use the full
server source (`source_track` or `source_ticket`); live Web Audio effects and
linked/independent pitch and speed controls remain available.

`POST /api/stream` requires verified Telegram initData and track ownership. It
issues a reusable opaque bearer URL valid for three hours. Treat that URL as
private. Every media request rechecks file availability and user permissions.
Download tickets remain separate, short-lived attachments. Neither ticket type
is written into browser session storage. Audio imported from an existing media
ticket also opens directly in the studio without a second full browser download.

Phone text inputs use at least 16px text to avoid iOS focus zoom. Pinch zoom is
retained. Visual viewport changes keep the focused field above the keyboard and
temporarily hide bottom controls while typing.

Validation:

- `python -m unittest tests.test_miniapp`: authentication, user isolation,
  ticket reuse/expiry, inline audio and range responses.
- `scripts/verify_miniapp_ui.py`: Chromium/WebKit playback, studio processing,
  both tempo/pitch modes, native exports and app navigation with API fixtures.
- `scripts/verify_stream_player.py`: browser harness expects assets at
  `/src/miniapp` and a synthetic 60-second 192kbps MP3 at `/fixture.mp3`.
  Delays the transfer tail by five seconds and checks playback begins before
  completion; also simulates a smaller visual viewport while a field has focus.

These browser checks do not replace testing on a physical iPhone. Startup time
on a user's phone still depends on the connection, device and original source
availability when the server has no prepared file.
