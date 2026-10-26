# Named sounds and the DJ room

Open **Studio → My presets** to save a named sound. Settings are stored in the
existing SQLite `studio_presets` named state for the authenticated Telegram user.
Only validated sound controls are saved: no track IDs, private paths, source
tickets or crop positions. The same sounds appear in the bot's studio and
`/presets`. Applying one in chat processes the current owned audio as a full MP3.

Open **Studio → DJ room** for two independent decks. Load from the shared library
or search inside the picker. Each deck has live tempo, pitch, bass, highs and level,
three cue points, and 2/4/8-second slip-rolls. BPM is entered or tapped manually;
tempo matching aligns rates, not beat-grid phase. Cues and deck positions belong
to the open app session.

Both decks share the main AudioContext and cached worklet registrations. Separate
gain nodes use an equal-power crossfader with headroom and a final compressor.
The crossfader stays docked above mobile navigation and hides while typing.
Roll captures at most eight seconds per deck in a small audio-thread ring buffer.
It repeats that fragment while the source playhead keeps advancing; releasing it
returns to the running track. Loop-rate pitch compensation preserves independent
tone control. Pausing stops output, including an active roll.

**Record set** captures the DJ mix only, without microphone access. Native
MediaRecorder is preferred; AudioWorklet PCM/WAV recording is the compatibility
path. The capture stays in the open app until the user requests MP3 download or
save. MP3 conversion uses the existing authenticated studio pipeline. A cached
export is reused for download/save; saved sets enter the shared music library.
Save a set before closing/reloading the app. Existing studio duration/file quotas
and bounded in-memory recording apply.

Normal studio navigation, processing and the regular bot remain available.
Leaving the DJ room pauses its decks and stops recording; returning within the
same page restores those decks. Pending deck preparation is cancelled when leaving,
and a second load waits for the first rather than starting competing user jobs.

Validation:

- Preset API tests: authentication, user isolation, persistent settings, limits,
  validation, source/crop exclusion and shared bot rendering.
- `verify_dj_room.py`: actual mobile Chromium/WebKit UI, one shared context,
  crossfader levels, cues, roll, manual tempo matching, audible set recording,
  MP3 request reuse, shared-library save and a real-time chirp loop/pause check.
- `verify_dj_recordings.py`: actual browser WebM/WAV captures converted through
  production FFmpeg rendering, with preserved duration and nonempty MP3 output.

The test WebKit lacks native MediaRecorder and therefore exercises the PCM
fallback. These browser checks are not physical iPhone or Android testing.

Deployment adds `studio_presets.py`, `studio_presets_bot.py` and static DJ modules;
no database migration, paid API or new account is needed. Previous images ignore
the extra named-state rows safely if rolled back.
