"""Choose an explicit recording before downloading; callbacks keep immutable snapshots."""
import asyncio
import os
import re
import secrets
import time
from copy import deepcopy
import yt_dlp
from telegram import InlineKeyboardButton as Button
from ui_layout import comfortable_keyboard as Markup
from telegram.error import TelegramError, BadRequest
from operations import checkpoint, stage
from audio_presentation import send_music


def find_versions(query, limit=5):
    if type(limit) is not int or not 1<=limit<=10:raise ValueError('Invalid search limit')
    checkpoint()
    options = {"quiet": True, "no_warnings": True, "skip_download": True,
               "extract_flat": "in_playlist", "socket_timeout": 15, "retries": 1,
               "cookiefile": os.getenv("YTDLP_COOKIE_FILE") or None}
    from youtube_session import cookie_snapshot
    from download_cache import search_cache
    try:
        with cookie_snapshot(options.get('cookiefile')) as cookies:
            options['cookiefile']=cookies
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(f"ytsearch{limit}:" + query[:240], download=False)
    except Exception:
        checkpoint()
        cached=search_cache(query)
        if cached:return cached[:limit]
        from soundcloud_source import search as sc_search
        reserve=sc_search(query,limit)
        if not reserve:
            from jamendo_source import search
            reserve=search(query,limit)
        if reserve:
            search_cache(query,reserve)
            return reserve
        raise
    checkpoint()
    result, seen = [], set()
    for entry in (info or {}).get("entries") or []:
        if not isinstance(entry, dict):
            continue
        identifier = entry.get("id")
        if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9_-]{11}", identifier) or identifier in seen:
            continue
        if entry.get("is_live") or entry.get("live_status") == "is_live":
            continue
        duration = entry.get("duration")
        if isinstance(duration, (int, float)) and not 0 < duration <= 3600:
            continue
        seen.add(identifier)
        result.append({"url": "https://www.youtube.com/watch?v=" + identifier,
                       "title": str(entry.get("title") or "Аудио")[:180],
                       "artist": str(entry.get("uploader") or entry.get("channel") or "")[:120],
                       "duration": round(duration) if isinstance(duration, (int, float)) else None,
                       "cover": "https://i.ytimg.com/vi/" + identifier + "/hqdefault.jpg"})
    if not result:
        from soundcloud_source import search as sc_search
        result=sc_search(query,limit)
        if not result:
            from jamendo_source import search
            result=search(query,limit)
    if result:search_cache(query,result)
    return result[:limit]


def remember_request(context, song, mode):
    token = secrets.token_hex(5)
    requests = context.user_data.setdefault("version_requests", {})
    requests[token] = {"song": dict(song), "candidates": [], "mode": mode}
    while len(requests) > 8:
        requests.pop(next(iter(requests)))
    return token, requests[token]


def source_search(song, source):
    """A new, user-visible search uses the catalog identity, not a failed video."""
    origin = song.get('_catalog_song') or song
    query = song.get('_search_query') or ' '.join(str(origin.get(k) or '') for k in ('title', 'artist')).strip()
    cached = _source_checks.get((song.get('_availability_uid'), query, source))
    if cached and cached[0] > time.monotonic():
        return deepcopy(cached[1])
    if source == 'sc':
        from soundcloud_source import search
    elif source == 'jam':
        from jamendo_source import search
    elif source == 'yt':
        from recording_availability import verified_choices
        return verified_choices(find_versions(query,10),query,song.get('_availability_uid'))
    else:
        raise ValueError('Invalid recording source')
    from recording_availability import verified_choices
    return verified_choices(search(query,10),query,song.get('_availability_uid'))


def source_rows(token, request):
    selected = request.get('source')
    return [[Button('Версии ' + name, callback_data=f'ver:source:{token}:{source}')]
            for source, name in (('yt', 'YouTube'), ('sc', 'SoundCloud'), ('jam', 'Jamendo'))
            if source != selected and source in request.get('available_sources', [])]


_source_checks = {}


async def source_inventory(song, uid, known=None):
    """Only advertise providers with checked recordings for this exact query/owner."""
    origin = song.get('_catalog_song') or song
    query = song.get('_search_query') or ' '.join(str(origin.get(k) or '') for k in ('title', 'artist')).strip()
    async def check(source):
        key = (uid, query, source)
        cached = _source_checks.get(key)
        if known is not None and source in known:
            rows = known[source]
        elif cached and cached[0] > time.monotonic():
            return source, deepcopy(cached[1])
        else:
            try:
                rows = await asyncio.to_thread(source_search, dict(song, _availability_uid=uid), source)
            except Exception:
                checkpoint()
                rows = []
        # A YouTube lookup may return reserve records; those do not establish
        # availability of YouTube itself.
        from soundcloud_source import public_url
        from jamendo_source import identifier
        rows = [row for row in rows if
                (source == 'sc' and public_url(row.get('url'))) or
                (source == 'jam' and identifier(row.get('url'))) or
                (source == 'yt' and re.fullmatch(r'https://www\.youtube\.com/watch\?v=[A-Za-z0-9_-]{11}', row.get('url', '')))]
        _source_checks[key] = (time.monotonic() + (60 if rows else 20), deepcopy(rows))
        while len(_source_checks) > 1000:
            _source_checks.pop(next(iter(_source_checks)))
        return source, deepcopy(rows)
    return dict(await asyncio.gather(*(check(source) for source in ('yt', 'sc', 'jam'))))


def queue_recovery(request):
    if not request.get("queue_ref"):
        return []
    from link_queue import skip_button
    token,index=request["queue_ref"]
    return [[skip_button(token,index)],[Button("Отменить очередь",callback_data="batch:stop:"+token)]]


async def version_screen(update, context, text, markup):
    query = getattr(update, "callback_query", None)
    message = getattr(query, "message", None)
    if message:
        try:
            if getattr(message, "text", None):
                return await query.edit_message_text(text, reply_markup=markup)
            if getattr(message, "photo", None):
                return await query.edit_message_caption(caption=text, reply_markup=markup)
        except BadRequest as exc:
            if "not modified" in str(exc).lower():
                return message
        except TelegramError:
            pass
    result = await update.effective_message.reply_text(text, reply_markup=markup)
    if message and (getattr(message, "text", None) or getattr(message, "photo", None)):
        from track_card import retire_download_menus
        await retire_download_menus(update, context)
    return result


async def show_versions(update, context, token, request, *, exclude=None):
    rows = []
    for index, item in enumerate(request["candidates"]):
        if index == exclude or index in request.get("sent_indices", []) or index in request.get('failed_indices', []):
            continue
        duration = item.get("duration")
        seconds = round(duration) if isinstance(duration, (int, float)) else 0
        stamp = f" · {seconds // 60}:{seconds % 60:02d}" if seconds else ""
        label = item['title'][:45]
        if request.get('source') in ('sc', 'jam'):
            label = item['title'][:32] + ' · ' + str(item.get('artist') or '')[:24]
        rows.append([Button(f"{index + 1}. {label}{stamp}",
                            callback_data=f"ver:pick:{token}:{index}")])
    if not rows:
        rows.append([Button("🔄 Найти версии заново", callback_data=f"ver:refresh:{token}", style="primary")])
    if request.get("queue_ref"):
        from link_queue import skip_button
        batch,index=request["queue_ref"]
        rows += [[skip_button(batch,index)],[Button("Отменить очередь",callback_data="batch:stop:"+batch)]]
    rows += source_rows(token, request)
    rows.append([Button("← Поиск", callback_data="ui:search")])
    sources = {item.get('source', 'YouTube') for item in request['candidates']}
    source = next(iter(sources)) if len(sources) == 1 else 'YouTube'
    from i18n_ui import tr
    message = await version_screen(update, context, (f"Очередь · трек {request['queue_ref'][1]+1}\n" if request.get("queue_ref") else "") + ("🎧 Выбери другую версию" if exclude is not None else "🎧 Выбери версию") + '\n'+tr('Источник записи: YouTube').replace('YouTube',source),
                                                    Markup(rows))
    if type(getattr(message, "message_id", None)) is int:
        request.setdefault("menu_messages", []).append([update.effective_chat.id, message.message_id])
    request["menu_messages"] = request.get("menu_messages", [])[-8:]
    return message


async def request_versions(update, context, song, *, mode="studio", queue_ref=None, automatic=None, source=None):
    token, request = remember_request(context, song, mode)
    if source: request['source'] = source
    if queue_ref:
        request["queue_ref"] = list(queue_ref)
    origin = getattr(getattr(update, "callback_query", None), "message", None)
    sender = getattr(origin, "from_user", None)
    if origin and type(getattr(origin, "message_id", None)) is int and sender and sender.is_bot:
        request["menu_messages"] = [[update.effective_chat.id, origin.message_id]]
    await stage("Ищу версии…")
    try:
        from jamendo_source import identifier
        if source:
            candidates = await asyncio.to_thread(source_search, dict(song,_availability_uid=update.effective_user.id), source)
        else:
            candidates = [dict(song)] if identifier(song.get('url')) else await asyncio.to_thread(find_versions, " ".join(
                str(song.get(key) or "") for key in ("title", "artist")).strip(),limit=10)
            from recording_availability import verified_choices
            candidates=await asyncio.to_thread(verified_choices,candidates,' '.join(str(song.get(k) or '') for k in ('title','artist')),update.effective_user.id)
        checkpoint()
    except Exception:
        inventory = await source_inventory(song, update.effective_user.id, {source or 'yt': []})
        request['available_sources'] = [key for key, rows in inventory.items() if rows]
        return await version_screen(update, context,
            "Не удалось найти версии. Попробуй ещё раз.", Markup(queue_recovery(request) + source_rows(token, request) + [
                [Button("🔄 Повторить поиск", callback_data=f"ver:refresh:{token}", style="primary")],
                [Button("← Поиск", callback_data="ui:search")]]))
    request["candidates"] = candidates
    known = {source or 'yt': candidates}
    inventory = await source_inventory(song, update.effective_user.id, known)
    request['available_sources'] = [key for key, rows in inventory.items() if rows]
    if not candidates:
        return await version_screen(update, context,
            "Не нашёл подходящие версии. Можно повторить поиск или уточнить название.", Markup(queue_recovery(request) + source_rows(token, request) + [
                [Button("🔄 Повторить поиск", callback_data=f"ver:refresh:{token}")],
                [Button("🔎 Уточнить название", callback_data="ui:search", style="primary")]]))
    if automatic:
        from search_quality import normalize
        wanted = set(normalize(str(song.get("title") or "")).split())
        artist = set(normalize(str(song.get("artist") or "")).split())
        def score(item):
            title_words=set(normalize(item["title"]).split())
            all_words=title_words | set(normalize(item["artist"]).split())
            overlap=len(wanted & title_words)/max(1,len(wanted))
            singer=len(artist & all_words)/max(1,len(artist))
            unwanted={"remix","cover","karaoke","live","slowed","sped","instrumental"}-wanted
            penalty=bool(unwanted & title_words)
            return overlap+singer-penalty
        ranked=sorted(enumerate(candidates),key=lambda pair:score(pair[1]),reverse=True)
        index,item=ranked[0]
        # Never silently send a recording whose title does not match the catalog.
        if wanted and wanted <= set(normalize(item["title"]).split()) and artist and artist <= set(normalize(item["title"]+" "+item["artist"]).split()):
            return await download_selected(update,context,token,request,index,*automatic)
    return await show_versions(update, context, token, request)


async def choose_version(update, context, downloader, metadata, retain, studio):
    query = update.callback_query
    duplicate = re.fullmatch(r"ver:pick:([0-9a-f]{10}):([0-4])", query.data or "")
    previous = context.user_data.get("version_requests", {}).get(duplicate[1], {}) if duplicate else {}
    if duplicate and int(duplicate[2]) in previous.get("sent_indices", []):
        return await query.answer("Этот трек уже отправлен выше.")
    await query.answer()
    provider = re.fullmatch(r'ver:source:([0-9a-f]{10}):(yt|sc|jam)', query.data or '')
    if provider:
        request = context.user_data.get('version_requests', {}).get(provider[1])
        if not request:
            return await update.effective_message.reply_text('Выбор устарел. Открой варианты ещё раз.')
        if request.get('queue_ref'):
            from link_queue import current
            if not current(context, *request['queue_ref']):
                return await update.effective_message.reply_text('Очередь уже завершена или отменена.')
        return await request_versions(update, context, request['song'], mode=request.get('mode', 'studio'),
                                      queue_ref=request.get('queue_ref'), source=provider[2])
    recovery = re.fullmatch(r"ver:(refresh|other):([0-9a-f]{10})(?::([0-4]))?", query.data or "")
    if recovery:
        request = context.user_data.get("version_requests", {}).get(recovery[2])
        if not request:
            return await update.effective_message.reply_text("Это меню уже недоступно. Открой трек ещё раз.",
                reply_markup=Markup([[Button("← Поиск", callback_data="ui:search")]]))
        if request.get("queue_ref"):
            from link_queue import current
            if not current(context, *request["queue_ref"]):
                return await update.effective_message.reply_text("Очередь уже завершена или отменена.")
        if recovery[1] == "refresh":
            return await request_versions(update, context, request["song"], mode=request.get("mode", "studio"), queue_ref=request.get("queue_ref"), source=request.get('source'))
        return await show_versions(update, context, recovery[2], request,
                                   exclude=int(recovery[3]) if recovery[3] is not None else None)
    match = re.fullmatch(r"ver:pick:([0-9a-f]{10}):([0-4])", query.data or "")
    request = context.user_data.get("version_requests", {}).get(match[1]) if match else None
    index = int(match[2]) if match else -1
    if not request or not 0 <= index < len(request["candidates"]):
        return await update.effective_message.reply_text("Выбор устарел. Открой варианты ещё раз.")
    if request.get("queue_ref"):
        from link_queue import current
        if not current(context, *request["queue_ref"]):
            return await update.effective_message.reply_text("Этот трек очереди уже обработан или отменён.")
    if request.get("queue_ref"):
        from operations import _current
        op = _current.get()
        if op:
            queue = current(context, *request["queue_ref"])
            queue["op_token"] = op.token
    return await download_selected(update, context, match[1], request, index, downloader, metadata, retain, studio)


async def download_selected(update, context, token, request, index, downloader, metadata, retain, studio):
    candidate = dict(request["candidates"][index])
    await stage("Скачиваю…")
    path = None
    sent = False
    # Keep the recording choices reachable without leaving obsolete download menus.
    other_rows = ([[Button("🎧 Другая версия", callback_data=f"ver:other:{token}:{index}")]]
                  if not request.get("queue_ref") and any(
                      i != index and i not in request.get("sent_indices", []) and i not in request.get('failed_indices', [])
                      for i in range(len(request["candidates"]))) else [])
    try:
        if request.get('mode') in ('listen','queue'):
            from audio_presentation import send_cached_music
            from track_card import card_keyboard, retire_download_menus
            resolved=dict(request['song'],url=candidate['url'],title=candidate['title'],artist=candidate.get('artist',''))
            if await send_cached_music(context.bot,update.effective_chat.id,candidate['url'],resolved['title'],resolved['artist'],reply_markup=card_keyboard(context,resolved,extra_rows=other_rows,delivered=True)):
                request.setdefault('sent_indices',[]).append(index)
                await retire_download_menus(update,context,request)
                return True
        from media_recovery import download_with_reserve
        path, info = await asyncio.to_thread(download_with_reserve,downloader,candidate['url'],candidate)
        checkpoint()
        title, artist = metadata(info)
        title = title or candidate["title"]
        artist = artist or candidate["artist"] or request["song"].get("artist")
        await stage("Отправляю…")
        resolved = dict(request["song"], title=title, artist=artist or "",
                        url=info.get('source_url') or candidate["url"], source=info.get('source') or candidate.get('source','YouTube'),license_url=info.get('license_url'), cover=candidate.get("cover") or request["song"].get("cover"))
        kwargs = {}
        if request.get("mode") in ("listen", "queue"):
            from track_card import card_keyboard
            kwargs["reply_markup"] = card_keyboard(context, resolved, extra_rows=other_rows, delivered=True)
        await send_music(context.bot, update.effective_chat.id, path, title, artist,
                         resolved.get("cover"), source_url=resolved['url'],license_url=resolved.get('license_url'), **kwargs)
        sent = True
        request.setdefault("sent_indices", []).append(index)
        from track_card import retire_download_menus
        await retire_download_menus(update, context, request)
        await retain(context, update.effective_user.id, path)
        context.user_data["downloaded_song"] = dict(request["song"], title=title, artist=artist or "",
                                                   url=resolved['url'],source=resolved.get('source'),license_url=resolved.get('license_url'))
        context.user_data["pending_effects"] = []
        if request.get("mode") not in ("listen", "queue"):
            await studio(update, context)
        return True
    except Exception as error:
        if sent:
            await update.effective_message.reply_text("Трек отправлен, но студию открыть не удалось.",
                reply_markup=Markup([[Button("🎛 Открыть студию", callback_data="studio:home")]]))
        else:
            if index not in request.setdefault('failed_indices', []): request['failed_indices'].append(index)
            from diagnostics import source_access_blocked, SOURCE_ACCESS_MESSAGE
            if source_access_blocked(error):
                if request.get('source') not in ('sc', 'jam'):
                    # Preserve the original catalog song; these are explicit new choices,
                    # never a silent replacement for the failed YouTube recording.
                    await request_versions(update, context, request['song'], mode=request.get('mode', 'studio'),
                                           queue_ref=request.get('queue_ref'), source='sc')
                    return False
                await version_screen(update, context, SOURCE_ACCESS_MESSAGE,
                    Markup(queue_recovery(request) + other_rows + source_rows(token, request) + [[Button("← Поиск", callback_data="ui:search")]]))
                return False
            await version_screen(update, context, "Не удалось скачать трек. Попробуй ещё раз или выбери другую версию.",
                Markup(queue_recovery(request) + source_rows(token, request) + [
                    [Button("🔄 Повторить", callback_data=f"ver:pick:{token}:{index}", style="primary")],
                    [Button("🎧 Другая версия", callback_data=f"ver:other:{token}:{index}")],
                    [Button("← Поиск", callback_data="ui:search")]]))
    finally:
        if path and os.path.isfile(path):
            from scratch import remove_owned_file
            remove_owned_file(path)
            if os.path.isfile(path): os.remove(path)
