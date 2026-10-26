# Studio playback and shared library

The linked tempo/pitch mode updates native playback as either slider moves.
It does not submit render jobs, reload the media source, or rewrite the active
slider's value during a drag. Native rate and pitch-preservation properties are
only assigned when they change.

Independent pitch uses a local AudioWorklet on supporting browsers. The streamed
source remains unchanged while tempo, pitch and live effects change. No new
server render/download is submitted for independent pitch adjustments. Native
tempo preserves input pitch; the worklet shifts that stable-pitch stream. This
avoids inconsistent native `preservesPitch=false` behavior across browser engines.
If the worklet cannot initialize, the existing full-track server pitch path and
bounded prepared-variant cache remain the compatibility fallback.
The separate explicit quick-preview button still provides a short effects sample;
full apply, save and export always use the original server source and settings.

Mobile and WebKit native rate writes are coalesced over 40ms. Effect racks crossfade
over 45ms instead of disconnecting abruptly, room changes debounce 160ms, and
mobile studio decorations avoid expensive compositing. The worklet keeps a small
4096-frame output reserve and fades its first block after an explicit seek/source
reset. These buffers add latency; this is not a zero-latency DAW. Reverse, mastering,
full export and other offline-only operations continue to use server processing.

Vendored SoundTouchJS audio-worklet 2.1.1 is MPL-2.0. See the license and notice in
`miniapp/`. Local processor patches reset queued samples, reserve output frames,
and soften startup/seek output. Original npm tarball integrity was verified.

The regular bot and Mini App share the authenticated user's language, saved
library, favorite flags and collections. Playlist changes preserve recordings
without automatically starring them. Removing a recording from the bot also
removes it from the app's saved library. Opening/returning to the app refreshes
its language and library from the shared state.

Private-chat track cards can open the selected recording directly in the Mini
App studio. The API resolves the user's own stored card or saved recording;
knowing another user's track ID does not grant access. Opening a card does not
automatically favorite it. App audio sent to chat includes the normal saved-track
and studio controls, with the card snapshot retained for later use.

Regression checks include `tests.test_miniapp`, `tests.test_playlists`,
`tests.test_track_card`, `scripts/verify_miniapp_ui.py` and
`scripts/verify_full_tone.py`. The latter uses the same isolated MP3 fixture setup
as `verify_stream_player.py`, checks playback beyond 15 seconds, rapid pitch
changes, cached variants, both linked slider drags without source reloads or
server jobs, language refresh and selected-track studio links in Chromium/WebKit.
`verify_full_tone.py` explicitly blocks the worklet to exercise the compatibility
path. `verify_mobile_audio.py` exercises actual worklet audio, a 440Hz signal shifted
to about 220Hz at independent tempo 1.5, slow-down drags, graph crossfades, queued
room changes, exact source position, and mobile Chromium with 4x main-thread CPU
throttling. These are browser-engine checks, not physical iPhone/Android testing.
