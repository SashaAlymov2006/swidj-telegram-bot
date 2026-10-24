# Validation

The clean publication copy passed 170 offline tests and dependency/cache checks on 2026-10-24. No production Telegram messages or paid API calls were made. Docker Compose validates without resolving a private environment file.

Public-source smoke checks were run separately during development for TikTok, Instagram and a Yandex metadata-to-full-recording flow. External sources can change; these checks do not guarantee availability for every URL or establish a load benchmark.

Bass control validation: stereo multi-tone audio checks verify ordered bass strength, preserved duration and no clipped PCM samples. UI tests verify exclusive levels, preview invalidation, reset, and English labels. Telegram SDK coverage exercises bass preview and full-track export.

Mini App: authenticated API isolation/expiry, shared locks, persistent playlists, controlled bot handoff and maintenance tests. Isolated Chromium checks passed desktop/mobile layout, actual playback, preview and WAV export, search, playlists/favorites, RU/EN and escaped user titles with no page errors. Real Telegram WebView testing over HTTPS is still pending.
