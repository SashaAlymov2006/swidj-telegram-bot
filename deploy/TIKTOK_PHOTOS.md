# TikTok photo posts

TikTok share links can refer to a photo post with a soundtrack rather than a
video. The bot and Mini App now support this format separately from the normal
video extractor. MP4 output is a slideshow of all photos with the post's music;
MP3 output is the available soundtrack. It is not an original uploaded video.

The handler reads publicly available structured post metadata, verifies the post
ID, and accepts media only from allowlisted TikTok CDNs. It does not use YouTube,
Jamendo, Google cookies, account pools, CAPTCHA solving or proxy rotation.

Frames retain their proportions, use a consistent canvas, and are encoded as
H.264/AAC for phones. Each photo is shown for at least three seconds. Shorter
soundtracks repeat to cover the slideshow. Temporary inputs are removed by the
owning operation; cached final files use the existing bounded user cache.

The shared link parser also accepts TikTok addresses without a scheme, invisible
copy/paste formatting marks, quoted share text and accidentally duplicated links.
Host/path validation remains strict. The app reads the current input value when
submitting, including when mobile paste did not trigger an input event.

Tests cover exact post identity, CDN validation, frame order, portrait proportions,
full video/audio duration, frontend paste handling and both app/chat import paths.
Unavailable or access-restricted posts still cannot be guaranteed to download.
