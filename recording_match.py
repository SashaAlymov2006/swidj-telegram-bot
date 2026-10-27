"""Conservative identity checks shared by independent recording reserves."""
import math
import re
import unicodedata

def norm(value):
    return ' '.join(re.findall(r'[^\W_]+',unicodedata.normalize('NFKC',str(value)).casefold()))

def identity(item):
    title=str(item.get('track') or item.get('title') or '')
    artists=item.get('artists')
    artist=str(item.get('artist') or (artists[0] if isinstance(artists,list) and len(artists)==1 else '') or item.get('uploader') or '')
    artist=re.sub(r'\s*-\s*Topic$','',artist,flags=re.I).strip()
    # Remove presentation labels, retaining remix/live/slowed/cover qualifiers.
    title=re.sub(r'\((?:official(?: music)? (?:video|audio)|lyrics?|lyric video)\)|\[(?:official(?: music)? (?:video|audio)|lyrics?|lyric video)\]','',title,flags=re.I).strip()
    parts=re.split(r'\s+[-–—]\s+',title,maxsplit=1)
    if len(parts)==2 and norm(parts[0])==norm(artist):title=parts[1]
    return norm(title),norm(artist)

def matches(hint,item):
    title,artist=identity(hint)
    if not title or not artist or identity(item)!=(title,artist):return False
    durations=[hint.get('duration'),item.get('duration')]
    return all(type(d) in (int,float) and math.isfinite(d) and d>0 for d in durations) and abs(durations[0]-durations[1])<=3
