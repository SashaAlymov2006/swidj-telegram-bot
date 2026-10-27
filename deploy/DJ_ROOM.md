# Named sounds and the DJ room

Open **Studio → My presets** to save a named sound. Settings are stored in the
existing SQLite `studio_presets` named state for the authenticated Telegram user.
Only validated sound controls are saved: no track IDs, private paths, source
tickets or crop positions. The same sounds appear in the bot's studio and
`/presets`. Applying one in chat processes the current owned audio as a full MP3.

Open **Studio → DJ room** for two independent decks. Load from the shared library
or search inside the picker. Each deck has live tempo, pitch, bass, highs and level,
three cue points, and 2/4/8-second slip-rolls. Local analysis estimates BPM and the beat-grid offset, with manual BPM, Tap,
half/double tempo, and a ?beat here? correction. Automatic analysis runs in the
background after a streamed track loads; it never blocks playback. Tempo matching
changes rate; Align beats briefly prepares/seeks only the follower against the
other deck's media clock, committing mobile rate updates before the seek. The
reference keeps playing. It is an assist, not guaranteed sample-accurate DJ sync.
On phones, A/B tabs expose one deck's controls while both continue playing.

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

## Rhythm, waveform and bar loops

`dj_studio.py` derives a 1200-point overview and 100 Hz onset energy from mono
2 kHz PCM using local FFmpeg. It analyzes the strongest 90-second window within
the first three minutes and estimates 60?182 BPM via normalized autocorrelation.
Low-confidence/silent input yields no BPM; half/double and beat-here correction
are available. This is an estimated beat grid, not musical downbeat detection.
Waveform click seeks; cue placement snaps to that grid. A light beat strip and
playhead update at 5 Hz; no full-track decoding in the phone browser.

Quantized loops capture forward from the next grid beat in 4/4: 1, 2, 4 or 8 bars.
The first pass records the fragment, then repeats it on the audio thread. This
is a slip loop: the underlying source keeps running, and release returns to it.
Tempo and pitch remain independent. Loop buffers are allocated on the main thread
and transferred without copying; at most 64 seconds per deck, allocated on demand.
At extremely slow tempos, choose fewer bars. The existing backward-looking Roll
remains separate. Seeking or cue recall releases either loop.

Per-deck transition FX: bipolar low/high-pass filter, continuous 0?30 dB bass cut,
and tempo-timed damped Echo Out. Parameters ramp on the audio clock. Restore sound
or reset effects without replacing/re-rendering the media source. FX enter the
same master limiter/recording bus as the decks.

## Saved projects

Authenticated GET/POST `/api/dj/projects` persists up to 12 named set projects per
user in SQLite `named_state.dj_projects`. A project holds owned track references,
positions, three cues, corrected beat grids, tempo/pitch/EQ, transition controls
and crossfader. It stores no stream tickets or browser blobs and duplicates no
audio. API responses expose only public track metadata. Project references remain
resolvable when they leave recent history. A missing cached recording may need
preparation through the existing provider pipeline. Save local uploads to My music
first. Open is confirmed, restores decks paused, and does not auto-play. Recording
and live loop state are deliberately separate from project settings.

Analysis authenticates ownership before every cache hit; only an owned prepared
source is copied under the existing user lock. A single analysis slot and at most
three pending users bound CPU/temp storage. Source studio quotas apply. Derived
JSON is capped at 400 files; keys include file identity/size/mtime plus algorithm
version, and never appear in the public response. No paid API or new dependency.

Additional verification: `test_dj_studio.py` known 90/120/150 BPM with phase,
silence/sustained-tone rejection, actual FFmpeg/cache behavior, project persistence
and cross-user access rejection. Extended `verify_dj_room.py` exercises waveform,
bar loops, alignment, audible filters, Echo Out and saved-project reload on mobile
Chromium/WebKit. `verify_dj_loop.py` verifies forward capture/release/pause with
real audio-thread chirps in both engines. Physical phone testing is still needed.
