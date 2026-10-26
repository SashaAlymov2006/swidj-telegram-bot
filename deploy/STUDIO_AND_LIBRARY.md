# Studio playback and shared library

The linked tempo/pitch mode updates native playback as either slider moves.
It does not submit render jobs, reload the media source, or rewrite the active
slider's value during a drag. Native rate and pitch-preservation properties are
only assigned when they change.

Independent pitch is automatically prepared for the **full original track** at
speed 1. The existing audio keeps playing until the replacement is ready. Native
tempo changes and live effects operate on that full pitch source, so changing
tempo does not require another pitch render. The last eight prepared pitch
variants can be reused for a bounded period in the open app. Obsolete results
are ignored after a newer pitch is selected or the current track changes.
The separate explicit quick-preview button still provides a short effects sample;
full apply, save and export always use the original server source and settings.

Full independent pitch requires server CPU time. It is not an instantaneous
local pitch shifter; sufficient disk/RAM alone cannot make initial rendering
instant. Playback continues while the server works.

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
