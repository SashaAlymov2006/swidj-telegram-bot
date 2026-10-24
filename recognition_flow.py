"""Recognition fallback policy, tested without contacting providers."""
import asyncio


async def identify(path, providers, timeout=35):
    attempts = []
    for name, provider in providers:
        try:
            result = await asyncio.wait_for(provider(path), timeout=timeout)
        except (Exception, asyncio.TimeoutError):
            attempts.append((name, 'unavailable'))
            continue
        if isinstance(result, dict) and all(
            isinstance(result.get(key), str) and result[key].strip()
            for key in ('title', 'artist')
        ):
            return result, attempts + [(name, 'matched')]
        attempts.append((name, 'no_match'))
    return None, attempts
