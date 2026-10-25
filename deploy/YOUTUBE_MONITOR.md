# Administrator notifications

The optional VPS monitor checks a public YouTube recording using the configured private session every 30 minutes. It requests metadata and formats without downloading audio or video. The check uses a temporary private cookie copy and does not rewrite the live session file.

Two consecutive authorization failures produce an owner alert. Three consecutive temporary failures produce a different alert; a network error is not reported as expired cookies. One recovery notification follows a confirmed incident. Alerts go only to `OWNER_USER_IDS` from the private server `.env`. No routine startup message is sent. State survives bot restarts in `/opt/swidj-private/youtube-monitor/state.json`.

For a deployment at `/opt/swidj`, install the service and timer from this directory into `/etc/systemd/system`, then run `systemctl daemon-reload` and `systemctl enable --now swidj-youtube-health.timer`. Run `systemctl start swidj-youtube-health.service` for the first check. Inspect the service journal and timer status for operation; credentials must never be printed or committed.

The monitor detects a failed control request; it cannot guarantee access to every recording or renew a Google login. Authentication challenges and account confirmation still require the account owner. Disable the timer with `systemctl disable --now swidj-youtube-health.timer` before planned extended maintenance if alerts are unwanted.

## Dedicated server browser session

With the optional private server browser configured, install `youtube_session_sync.py` beside `youtube_health.py`. Before each scheduled check, the service exports only unexpired `youtube.com` cookies from that dedicated profile. A missing or unauthenticated browser profile leaves the previous export intact. The new export is written atomically, with restrictive permissions, outside the repository and recovery archives.

The bot uses `YTDLP_COOKIE_FILE=/run/youtube/cookies-server-session.txt` with the private YouTube directory mounted into its container. Each downloader and search request works with a disposable cookie snapshot, so downloader cookie-jar writes cannot modify the shared export. Temporary copies are removed on success and failure.

This synchronizes an existing session; it does not sign into Google, complete challenges, or guarantee a permanent session. Keep the browser profile private and exclude it, exported cookies, and all login data from Git and backups. The browser web interface must remain bound to server localhost and accessed through an authorized administrator connection.
