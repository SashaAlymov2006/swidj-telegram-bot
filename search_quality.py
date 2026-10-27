"""Conservative catalog ranking: boost exact matches, preserve other source order."""
import re
import unicodedata


def normalize(value):
    value = unicodedata.normalize("NFKC", value).casefold().replace("ё", "е")
    return " ".join(re.findall(r"[^\W_]+", value, flags=re.UNICODE))


VARIANT_WORDS = frozenset(('remix','cover','karaoke','slowed','sped','nightcore','mashup',
                          'instrumental','reverb','boosted','acoustic','live','extended','spedup',
                          'ремикс','кавер','замедленная','ускоренная','минус','инструментал'))


def recording_choices(items, query, limit=3):
    """Compact relevant originals; modified versions require explicit query words."""
    wanted=set(normalize(str(query)).split())
    for synonyms in ({'remix','ремикс'},{'cover','кавер'},{'slowed','замедленная'},
                     {'sped','spedup','speed','ускоренная','ускоренное','ускорить'},
                     {'instrumental','инструментал','минус'}):
        if wanted&synonyms:wanted|=synonyms
    accepted=[];seen=set()
    for item in items:
        title=set(normalize(str(item.get('title') or '')).split())
        if (title & VARIANT_WORDS)-wanted:continue
        label=normalize(str(item.get('title') or ''))
        if re.search(r'\bspeed up\b',label) and not wanted&{'speed','sped','ускоренная','ускоренное','ускорить'}:continue
        timed=r'\b\d+\s+(?:minutes?|hours?|минут\w*|час\w*)\b'
        if re.search(timed,label) and title&{'version','loop','repeat','версия','повтор'} and not re.search(timed,normalize(str(query))):continue
        url=item.get('url')
        if not url or url in seen:continue
        seen.add(url);accepted.append(item)
    def score(item):
        title=normalize(str(item.get('title') or ''))
        words=set((title+' '+normalize(str(item.get('artist') or ''))).split())
        overlap=len(words&wanted)/max(1,len(wanted))
        # Prefer the song audio over a music video with additional intro/outro.
        official_audio=bool(re.search(r'\bofficial audio\b',title))
        return overlap,official_audio
    return sorted(accepted,key=score,reverse=True)[:limit]


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
