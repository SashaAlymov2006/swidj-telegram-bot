# Administrator notifications

The optional VPS monitor checks a public YouTube recording using the configured private session every 30 minutes. It requests metadata and formats without downloading audio or video. The check uses a temporary private cookie copy and does not rewrite the live session file.

Two consecutive authorization failures produce an owner alert. Three consecutive temporary failures produce a different alert; a network error is not reported as expired cookies. One recovery notification follows a confirmed incident. Alerts go only to `OWNER_USER_IDS` from the private server `.env`. No routine startup message is sent. State survives bot restarts in `/opt/swidj-private/youtube-monitor/state.json`.

For a deployment at `/opt/swidj`, install the service and timer from this directory into `/etc/systemd/system`, then run `systemctl daemon-reload` and `systemctl enable --now swidj-youtube-health.timer`. Run `systemctl start swidj-youtube-health.service` for the first check. Inspect the service journal and timer status for operation; credentials must never be printed or committed.

The monitor detects a failed control request; it cannot guarantee access to every recording or renew a Google login. Authentication challenges and account confirmation still require the account owner. Disable the timer with `systemctl disable --now swidj-youtube-health.timer` before planned extended maintenance if alerts are unwanted.
