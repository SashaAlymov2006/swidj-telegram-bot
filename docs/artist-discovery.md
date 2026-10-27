# Artist discovery

Artist searches are separate from alternate recordings of one song. Mini App offers an artist catalog when an artist name matches returned metadata; track cards also open the artist. Chat has a Track / artist info action and paged artist lists.

Public catalogs: YouTube, SoundCloud, Audius and Jamendo. Results merge in pages of ten with optional source filters. Discovery is bounded to fifty results per provider, cached for ninety seconds, and deduplicated by recording URL. It is not an exhaustive discography or an assertion that similarly named accounts are verified identities. SoundCloud combines the matching public uploader profile with keyword results, including copies posted by other accounts.

About this track displays only known metadata and a source link. Existing Audius/Jamendo credit and download eligibility checks remain. Catalog metadata can be browsed before playback availability is tested; availability can change upstream. Song version selection retains the existing checked compact list of up to five choices. YouTube video primary loader and jaky.dev fallback order are unchanged.

Validation: 376 offline tests in isolated Linux, JavaScript syntax and UI pagination/escaping checks. Authenticated live Mini App artist lookup, two pages without duplicate IDs, unchanged library counts; Telegram connectivity and database integrity checks passed. RU/EN chat callbacks tested with mocked messages, not physical-phone testing. Live SoundCloud GNEEDX query returned ten distinct titles followed by two more; merged live catalog returned two pages of ten across YouTube and SoundCloud.
