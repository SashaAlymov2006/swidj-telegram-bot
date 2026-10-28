# Search efficiency without reducing available choices

Chart resolution starts independent source inventories while primary extraction/preflight runs. Both branches are joined before returning the same response shape; source ordering and up to five choices remain. Availability samples, provider eligibility checks and global concurrency limits are retained.

Direct provider searches now retain checked results for sixty seconds (twenty seconds when empty), with their checked limit. A later request for more choices expands instead of mistaking a short list for a complete list. In-flight duplicates for the same effective owner/query/provider share a cancellable lock and cached result. Reference-counted locks are removed when unused. Bot operation identity is used when no explicit owner was supplied. Different owners remain independent; returned snapshots are copied.

Chart preflight receives the authenticated owner, enabling existing owned/public file-cache reuse. Chart result caches are owner-scoped to preserve isolation. No private files or playback permissions are shared across users by this optimization.

Measurements are not a speed guarantee: prior sequential chart pipeline took28.67–29.11s, including24.77s availability checks in one run. Candidate parallel pipeline took28.235s cold and0.557s warm. Live deployed endpoint took27.12s cold and0.517s warm, returning the same five choices. Most cold latency remains in genuine YouTube availability tests. Warm caching existed previously; this update improves reuse and eliminates duplicated work, not every cold network delay.

Validation:394 isolated Linux tests, including checked-result reuse/expansion, concurrent duplicates, canceled operations, effective owner identity, owner-scoped chart results and deterministic parallel-branch orchestration. Live authenticated search/charts, library integrity, multiple downloads and reserve audits documented in the private session report. No UI, payments, studio settings, download limits or provider order changes.
