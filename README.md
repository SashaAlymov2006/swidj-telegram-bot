# SwiDJ
### A bilingual Telegram music and audio toolkit

[Русская версия](README.ru.md) · [Architecture](docs/ARCHITECTURE.md) · [Demo guide](docs/DEMO.md)

SwiDJ brings music discovery, personal audio tools and public video retrieval into a compact Telegram conversation. This portfolio project focuses on practical user flows: send a link or audio file, get a result, then save it or work with it.

**Python · python-telegram-bot · FFmpeg · Whisper · yt-dlp · SQLite · Docker**

## What it does

| Area | Features |
| --- | --- |
| Discovery | Search by title or lyrics; transcribe spoken words for a song search |
| Music links | YouTube and SoundCloud audio; Spotify, Apple Music and Yandex Music links resolve song metadata and search for an available recording |
| Video | Public YouTube videos, TikTok videos and Instagram videos/Reels |
| Audio studio | Trim, convert, speed up, slowed/reverb, bass, reverse, loops and phone ringtone exports |
| Personal library | Favourites, playlists and saving users' own uploaded audio |
| Experience | Russian/English UI, remembered language, compact result navigation, retries and cancellation |
| Operations | Owner controls, persistent state, bounded caches and source/runtime backup utilities |

Catalog links do **not** extract protected audio from subscription services. When the title and artist match, the bot can automatically download a corresponding full YouTube recording; ambiguous results retain recording choices. Yandex metadata has an additional public Songlink fallback that validates the exact track ID. Availability depends on the source and network region.

Voice transcription is available locally. Commercial music recognition, reliable humming recognition and AI music generation are **not** completed free features; optional billable integrations are disabled by default.

## Quick start with Docker

Requirements: Docker Engine with Compose (or Docker Desktop using Linux containers), internet access, and your own Telegram bot token.

1. Clone this repository.
2. Copy the environment template:
   - Windows PowerShell: `Copy-Item .env.example .env`
   - macOS/Linux: `cp .env.example .env`
3. Set `TELEGRAM_TOKEN` in `.env` using a bot created with @BotFather.
4. Optionally set `GENIUS_TOKEN` for title/lyrics catalog search. Leave paid API keys empty.
5. Start:

```sh
docker compose up --build -d
docker compose logs --tail 50 bot
```

Open your bot in Telegram and send `/start`. Use `/language` to switch Russian/English.

```sh
docker compose stop       # stop, preserving volumes
docker compose up -d      # start again
```

Do not run two polling processes with the same bot token. Initial image builds and the first local speech-model download can take time. The Compose configuration limits the service to 2 CPUs and 8 GB RAM; heavy tasks share this budget.

## Configuration

| Variable | Purpose |
| --- | --- |
| `TELEGRAM_TOKEN` | Required; your bot token |
| `GENIUS_TOKEN` | Optional key for catalog search by title/lyrics |
| `OWNER_USER_IDS` | Comma-separated Telegram user IDs allowed into owner controls; empty by default |
| `WHISPER_MODEL` | Local transcription model; defaults to `medium` |
| `EXTERNAL_PAID_API_ENABLED` | Optional billable calls; disabled in the provided Compose configuration |
| `AUDIO_CACHE_DIR` | Persistent working audio cache |

Keep `.env`, cookies, user databases and backups private. Persistent data and model downloads use Docker volumes. The active audio cache targets 256 MiB / 24 hours; active jobs, saved uploads, model files and backups are separate and can use additional disk space.

## Verification

The current source passed **158 offline tests**, including Telegram SDK flows, language isolation, playlists, cancellation, recovery and media cleanup. This is functional test coverage, not a large-scale performance benchmark.

```sh
docker build -t swidj:test .
docker run --rm --network none --mount type=bind,source="$(pwd)",target=/workspace,readonly --workdir /workspace swidj:test python -m unittest discover -s tests -v
docker run --rm --network none swidj:test python -m pip check
```

On Windows, run the included verification script:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify_docker.ps1 -Image swidj:test
```

Offline tests use fake Telegram transport and fixture data. They never poll the real bot or call paid recognition APIs. Public-source smoke checks are separate and do not guarantee that every third-party URL will remain available.

## Project status

A working portfolio prototype, developed iteratively with AI assistance. It currently runs on a developer-managed machine; this repository does not promise an always-on public service. Payments and a Telegram Mini App are future work.

Only retrieve or process media you are authorized to use. Private posts, login-restricted content and unsupported carousel entries may be unavailable; video output is capped at 49 MiB.

See [architecture and engineering decisions](docs/ARCHITECTURE.md) and the [demo walkthrough](docs/DEMO.md).
