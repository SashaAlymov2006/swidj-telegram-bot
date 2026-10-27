"""Conservative catalog ranking: boost exact matches, preserve other source order."""
import re
import unicodedata
from difflib import SequenceMatcher


# Small phonetic vocabulary supplements general transliteration, not a song catalog.
_SOUND = dict(pair.split(':', 1) for pair in (
    'шейп:shape оф:of ю:you йу:you ай:i вонт:want уонт:want ит:it зэт:that '
    'зет:that вэй:way вей:way блайндинг:blinding лайтс:lights хелло:hello '
    'хэлло:hello лав:love лов:love ми:me май:my найт:night найтс:nights '
    'донт:dont дэнс:dance денс:dance виз:with энд:and зе:the зэ:the '
    'ин:in он:on ту:to фор:for фром:from би:be бэби:baby бейби:baby '
    'нью:new невэр:never невер:never гив:give ап:up лет:let гоу:go '
    'стаи:stay стей:stay дрим:dream дримс:dreams тайм:time саммер:summer '
    'эд:ed ширан:sheeran уикенд:weeknd викенд:weeknd шиверс:shivers '
    'дойчланд:deutschland дойч:deutsch их:ich дих:dich либе:liebe '
    'либе:liebe нихт:nicht майне:meine айн:ein айнэ:eine ду:du '
    'жё:je же:je тэм:taime тем:taime тэйм:taime амур:amour '
    'бонжур:bonjour авек:avec пур:pour тужур:toujours '
    'ласшате:lasciatemi лашате:lasciate ласшатэ:lasciate '
    'кантаре:cantare кантарэ:cantare воларе:volare аморе:amore '
    'белла:bella чао:ciao итальяно:italiano феличита:felicita '
    'деспасито:despacito корасон:corazon байландо:bailando'
).split())
_LATIN = dict(zip('абвгдеёзийклмнопрстуфхыэ',
                  ('a','b','v','g','d','e','yo','z','i','y','k','l','m','n','o','p','r','s','t','u','f','kh','y','e')))
_LATIN.update({'ж':'zh','ц':'ts','ч':'ch','ш':'sh','щ':'shch','ю':'yu','я':'ya','ь':'','ъ':''})
_KEYS = str.maketrans(dict(zip('йцукенгшщзхъфывапролджэячсмитьбю', "qwertyuiop[]asdfghjkl;'zxcvbnm,.")))
_REVERSE_KEYS = str.maketrans(dict(zip("qwertyuiop[]asdfghjkl;'zxcvbnm,.",'йцукенгшщзхъфывапролджэячсмитьбю')))


def query_alternatives(query):
    """Bounded phonetic/keyboard hints, never replace the original request."""
    text=normalize(query)
    if not 4<=len(text)<=160 or '://' in query:return []
    if not re.search('[а-я]',text):
        letters=re.findall('[a-z]',text)
        repaired=text.translate(_REVERSE_KEYS)
        # Avoid converting ordinary Latin titles to meaningless Cyrillic.
        if len(letters)>=4 and sum(c in 'aeiouy' for c in letters)/len(letters)<=0.25 and sum(c in 'аеёиоуыэюя' for c in repaired)/len(letters)>=0.25:
            return [repaired]
        return []
    words=text.split()
    variants=[]
    letters=re.findall('[а-я]',text)
    if len(letters)>=4 and sum(c not in 'аеёиоуыэюяьъ' for c in letters)/len(letters)>=0.8:
        repaired=text.translate(_KEYS)
        if re.search('[a-z]{3}',repaired):variants.append(repaired)
    # Italian "lasciatemi" is often heard as two words in Russian.
    phonetic=re.sub(r'\b(?:ласшате|лашате|ласшатэ) ми\b','lasciatemi',text)
    converted=[''.join(_LATIN.get(c,c) for c in word) if word not in _SOUND else _SOUND[word] for word in phonetic.split()]
    variants.append(' '.join(converted))
    return list(dict.fromkeys(v for v in variants if v!=text))[:2]


def query_alternative(query):
    return next(iter(query_alternatives(query)),None)


def query_match(query, item):
    """Token coverage with conservative typo tolerance; preserve short exact words."""
    wanted=normalize(query).split()
    labels=normalize(str(item.get('title',''))+' '+str(item.get('artist',''))).split()
    if not wanted or not labels:return 0.0
    compact=''.join(wanted)
    if len(compact)>=5 and any(compact==''.join(normalize(str(item.get(key,''))).split()) for key in ('title','artist')):return 1.0
    def similarity(word):
        if word in labels:return 1.0
        if len(word)<4:return 0.0
        def plain(value):return ''.join(c for c in unicodedata.normalize('NFKD',value) if not unicodedata.combining(c))
        return max((SequenceMatcher(None,plain(word),plain(other)).ratio() for other in labels if len(other)>=4),default=0.0)
    return sum(similarity(word) for word in wanted)/len(wanted)


def assisted_search(search, query, *args):
    """Keep original results; only add relevant fallback when original is weak."""
    from operations import checkpoint
    checkpoint();rows=search(query,*args)
    # Catalog search engines already tolerate Latin typos. Locally boost close hits
    # without changing the query or adding requests for well-formed Latin searches.
    alternatives=query_alternatives(query)
    exact=normalize(query)
    if any(exact in (normalize(str(row.get('title',''))),normalize(str(row.get('artist',''))),normalize(str(row.get('title',''))+' '+str(row.get('artist',''))),normalize(str(row.get('artist',''))+' '+str(row.get('title','')))) for row in rows):return rows
    phonetic_words=normalize(query).split()
    known_sound=bool(phonetic_words) and sum(word in _SOUND for word in phonetic_words)/len(phonetic_words)>=0.5
    if not known_sound and any(query_match(query,row)>=0.88 for row in rows):return rows
    if not alternatives:return sorted(rows,key=lambda row:query_match(query,row),reverse=True)
    accepted=[]
    for alternative in alternatives:
        checkpoint()
        try:extra=search(alternative,*args)
        except Exception:
            checkpoint();continue
        checkpoint()
        accepted=[dict(row,_search_interpretation=alternative) for row in extra if query_match(alternative,row)>=0.78]
        if accepted:break
    if not accepted:return rows
    seen=set();merged=[]
    # Original exact hits were handled above. Retain weaker originals after matches.
    for row in sorted(accepted,key=lambda row:query_match(alternative,row),reverse=True)+rows:
        key=row.get('url') or (row.get('id'),row.get('title'),row.get('artist'))
        if key not in seen:seen.add(key);merged.append(row)
    return merged


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
        interpreted=set(normalize(item.get('_search_interpretation') or '').split())
        overlap=max(len(words&wanted)/max(1,len(wanted)),len(words&interpreted)/max(1,len(interpreted)))
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
        approximate=query_match(song.get('_search_interpretation') or query,song)
        if approximate>=0.78:return approximate*0.9
        return 0
    return sorted(results, key=score, reverse=True)
