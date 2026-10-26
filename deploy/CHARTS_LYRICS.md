# Chart freshness and lyrics

Country Top 50 feeds come from Apple Music; positions and publication time are
provided by that source, independently of users' searches. The server checks all
six countries hourly, starting one minute after launch. Requests reuse data for
30 minutes. Disk cache survives restarts; provider failure can return the last
successful country feed for up to seven days, explicitly marked as cached.

The Mini App rechecks visible charts after 30 minutes, including when returning
to the app. It avoids refreshing while the chart filter has keyboard focus or
a chart track is being prepared. The manual refresh button remains available.
Refreshing does not invent new rankings when the source's positions are unchanged.

Lyrics use LRCLIB without a paid API. Recording annotations and matching artist
prefixes are cleaned before lookup. Both plain and synchronized lyrics can be
displayed, with timestamps removed for reading. Duplicate results are collapsed.
An empty result is cached for two minutes, successful results for one hour.
Not every recording, remix or language has lyrics in the provider's catalog.
