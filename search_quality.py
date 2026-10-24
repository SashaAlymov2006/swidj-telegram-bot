"""Conservative catalog ranking: boost exact matches, preserve other source order."""
import re
import unicodedata


def normalize(value):
    value = unicodedata.normalize("NFKC", value).casefold().replace("ё", "е")
    return " ".join(re.findall(r"[^\W_]+", value, flags=re.UNICODE))


def merge_results(groups, query=""):
    results, seen = [], set()
    for group in groups:
        for song in group:
            key = (normalize(song["title"]), normalize(song["artist"]))
            if key not in seen:
                seen.add(key)
                results.append(song)
    wanted = normalize(query)
    if not wanted:
        return results
    def score(song):
        title, artist = normalize(song["title"]), normalize(song["artist"])
        if wanted in (f"{title} {artist}", f"{artist} {title}"):
            return 3
        if wanted == title:
            return 2
        if wanted == artist:
            return 1
        return 0
    return sorted(results, key=score, reverse=True)
