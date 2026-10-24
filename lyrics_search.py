"""Bounded phrase search and lyric verification; no paid model calls."""
import asyncio
from difflib import SequenceMatcher
import re
from urllib.parse import urlparse
from search_quality import normalize, merge_results
from operations import checkpoint


def phrases(text):
    cleaned = " ".join(text.split())[:300]
    words = cleaned.split()
    candidates = [cleaned]
    if len(words) > 8:
        candidates = [" ".join(words[:8]), " ".join(words[-8:])]
    return list(dict.fromkeys(value for value in candidates if value))


def lyric_score(text, query):
    wanted, document = normalize(query), normalize(text)
    if not wanted or not document:
        return 0
    if wanted in document:
        return 1.0
    words = document.split()
    target = wanted.split()
    if len(target) < 3:
        return 0
    return max((SequenceMatcher(None, target, words[index:index + len(target)]).ratio()
                for index in range(0, min(len(words), 5000))), default=0)


async def search_lyrics(query, genius, deezer, get_lyrics):
    variants = phrases(query)
    groups = await asyncio.gather(*(provider(value) for value in variants for provider in (genius, deezer)))
    checkpoint()
    songs = merge_results(groups)
    semaphore = asyncio.Semaphore(2)
    async def verify(song):
        host = (urlparse(song.get("url", "")).hostname or "").lower()
        if song.get("source", "Genius") != "Genius" or host not in ("genius.com", "www.genius.com"):
            return 0
        try:
            async with semaphore:
                text = await get_lyrics(song["url"])
            checkpoint()
            return max((lyric_score(text or "", value) for value in variants), default=0)
        except Exception:
            return 0
    subset = songs[:5]
    scores = await asyncio.gather(*(verify(song) for song in subset))
    ranked = list(zip(subset, scores)) + [(song, 0) for song in songs[5:]]
    ranked.sort(key=lambda item: item[1], reverse=True)
    return [dict(song, lyrics_match=score >= 0.8) for song, score in ranked]
