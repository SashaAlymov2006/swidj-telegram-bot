"""Saved tracks and playlists: one save action, short screens, old data preserved."""
import asyncio
from html import escape
import re
import secrets
from telegram import InlineKeyboardButton as Button
from ui_layout import comfortable_keyboard as Markup
from telegram.error import TelegramError, BadRequest

PAGE_SIZE = 5
MAX_TRACKS = 60


async def screen(update, text, rows):
    markup = Markup(rows)
    query = getattr(update, "callback_query", None)
    message = getattr(query, "message", None)
    if message and getattr(message, "text", None):
        try:
            return await query.edit_message_text(text, parse_mode="HTML", reply_markup=markup)
        except BadRequest as exc:
            if "not modified" in str(exc).lower():
                return
        except TelegramError:
            pass
    return await update.effective_message.reply_text(text, parse_mode="HTML", reply_markup=markup)


async def collections(context, uid, store):
    if "music_collections" not in context.user_data:
        saved = await asyncio.to_thread(store.load_named, "music_collections")
        context.user_data["music_collections"] = saved.get(uid, {})
    return context.user_data["music_collections"]


def all_saved(uid, favorites, folders):
    result, seen = [], set()
    for song in list(favorites.get(uid, [])) + [song for folder in folders.values() for song in folder["songs"]]:
        if song["id"] not in seen:
            seen.add(song["id"])
            result.append(dict(song))
    return result


async def commit(context, uid, store, favorites, folders):
    await asyncio.to_thread(store.save_library, uid, favorites.get(uid, []), folders)


async def save_collections(context, uid, store):
    await asyncio.to_thread(store.save_named, "music_collections", uid, context.user_data["music_collections"])


def clean_name(name):
    return " ".join(re.sub(r"[\x00-\x1f\x7f]", " ", name).split())[:40]


def find_song(uid, identifier, favorites, folders, results=None):
    sources = all_saved(uid, favorites, folders) + list((results or {}).get(uid, []))
    return next((song for song in sources if song["id"] == identifier), None)


async def show_library_home(update, context, favorites, store):
    folders = await collections(context, update.effective_user.id, store)
    count = len(all_saved(update.effective_user.id, favorites, folders))
    await screen(update, "⭐ <b>Моя музыка</b>\nТреки и плейлисты — всё здесь.", [
        [Button(f"🎵 Все сохранённые · {count}", callback_data="lib:page:0", style="primary")],
        [Button(f"🎧 Мои плейлисты · {len(folders)}", callback_data="lib:folders")],
        [Button(f"📂 Мои файлы · {sum(song.get('kind') == 'upload' for song in all_saved(update.effective_user.id, favorites, folders))}", callback_data="lib:uploads:0")],
        [Button("🔎 Найти музыку", callback_data="ui:search"), Button("← Меню", callback_data="ui:home")]])


async def show_folders(update, context, store):
    folders = await collections(context, update.effective_user.id, store)
    rows = [[Button(f"🎧 {value['name']} · {len(value['songs'])}", callback_data="lib:col:" + key)]
            for key, value in folders.items()]
    rows += [[Button("＋ Новый плейлист", callback_data="lib:new", style="success")],
             [Button("← Моя музыка", callback_data="lib:home")]]
    await screen(update, "🎧 <b>Мои плейлисты</b>" + ("\nСоздай первый — например, «Для работы»." if not folders else ""), rows)


async def show_favorites(update, context, favorites, page=0, uploads_only=False):
    songs = all_saved(update.effective_user.id, favorites, context.user_data.get("music_collections", {}))
    if uploads_only:
        songs = [song for song in songs if song.get("kind") == "upload"]
    page_prefix = "lib:uploads" if uploads_only else "lib:page"
    total = max(1, (len(songs) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total - 1))
    context.user_data["library_page"] = page
    rows = [[Button(f"{index}. {song['title']} — {song['artist']}"[:54], callback_data=f"lib:item:{song['id']}"),
             Button("Скачать", callback_data=f"lib:download:{song['id']}", style="primary"),
             Button("🗑", callback_data=f"lib:delete:{song['id']}")]
            for index, song in enumerate(songs[page * PAGE_SIZE:(page + 1) * PAGE_SIZE], page * PAGE_SIZE + 1)]
    navigation = []
    if page:
        navigation.append(Button("← Назад", callback_data=f"{page_prefix}:{page - 1}"))
    if page + 1 < total:
        navigation.append(Button("Дальше →", callback_data=f"{page_prefix}:{page + 1}"))
    if navigation:
        rows.append(navigation)
    rows += [[Button("🔎 Найти музыку", callback_data="ui:search"), Button("← Моя музыка", callback_data="lib:home")]]
    title = (f"📂 <b>Мои файлы</b> · {len(songs)}" if uploads_only else f"🎵 <b>Все сохранённые</b> · {len(songs)}") + (f"\n{page + 1} / {total}" if total > 1 else "")
    empty = "📂 <b>Твои файлы и ремиксы</b>\nОтправь аудио в чат и нажми «＋ Сохранить»." if uploads_only else "🎵 <b>Здесь будут твои треки</b>\nНайди песню или отправь свой файл и нажми «＋ Сохранить»."
    await screen(update, title if songs else empty, rows)


async def show_playlist(update, context, folders, key, page=0, notice=""):
    folder = folders.get(key)
    if not folder:
        return await screen(update, "Плейлист больше недоступен.", [[Button("← Плейлисты", callback_data="lib:folders")]])
    songs = folder["songs"]
    total = max(1, (len(songs) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total - 1))
    rows = [[Button(f"{index}. {song['title']}"[:54], callback_data=f"lib:ci:{key}:{song['id']}"),
             Button("Скачать", callback_data=f"lib:download:{song['id']}", style="primary"),
             Button("✕", callback_data=f"lib:cd:{key}:{song['id']}")]
            for index, song in enumerate(songs[page * PAGE_SIZE:(page + 1) * PAGE_SIZE], page * PAGE_SIZE + 1)]
    nav = []
    if page:
        nav.append(Button("←", callback_data=f"lib:col:{key}:{page - 1}"))
    if page + 1 < total:
        nav.append(Button("→", callback_data=f"lib:col:{key}:{page + 1}"))
    if nav:
        rows.append(nav)
    rows += [[Button("＋ Добавить треки", callback_data=f"lib:add:{key}:0", style="success")],
             [Button("Настройки", callback_data="lib:settings:" + key), Button("← Плейлисты", callback_data="lib:folders")]]
    text = ("✓ " + notice + "\n" if notice else "") + f"🎧 <b>{escape(folder['name'])}</b> · {len(songs)}"
    if total > 1:
        text += f"\n{page + 1} / {total}"
    if not songs:
        text += "\nДобавь музыку из сохранённых."
    await screen(update, text, rows)


async def save_song(update, context, song, favorites, store, *, offer_playlist=True):
    song = dict(song)
    song.pop("_search_page", None)
    uid = update.effective_user.id
    folders = await collections(context, uid, store)
    if song.get("kind") == "upload":
        from uploaded_media import retain_upload
        existing = find_song(uid, song["id"], favorites, folders)
        song = await retain_upload(update, context, existing or song)
    favorites[uid] = all_saved(uid, favorites, folders)
    if not any(item["id"] == song["id"] for item in favorites[uid]):
        favorites[uid].append(dict(song))
    await commit(context, uid, store, favorites, folders)
    if not offer_playlist:
        return
    rows = [[Button(("✓ " if any(item["id"] == song["id"] for item in folder["songs"]) else "🎧 ") + folder["name"],
                    callback_data=f"lib:save:{key}:{song['id']}")] for key, folder in folders.items()]
    rows += [[Button("＋ Новый плейлист", callback_data=f"lib:new:{song['id']}", style="success")],
             [Button("Готово", callback_data="lib:home", style="primary")]]
    await screen(update, f"✅ <b>Сохранено</b>\n{escape(song['title'])}\n\nДобавить в плейлист?", rows)


async def create_collection(update, context, store, name, favorites=None):
    uid = update.effective_user.id
    name = clean_name(name)
    if not name:
        return await screen(update, "Название плейлиста?", [[Button("Отмена", callback_data="lib:folders")]])
    folders = await collections(context, uid, store)
    if favorites is None:
        _, favorites = await asyncio.to_thread(store.load)
    favorites[uid] = all_saved(uid, favorites, folders)
    key = next((key for key, folder in folders.items() if folder["name"].casefold() == name.casefold()), None)
    if key is None:
        if len(folders) >= 30:
            return await screen(update, "Уже 30 плейлистов. Удали ненужный.", [[Button("← Плейлисты", callback_data="lib:folders")]])
        key = secrets.token_hex(4)
        folders[key] = {"name": name, "songs": []}
    pending = context.user_data.get("new_collection_song")
    if pending and not any(item["id"] == pending["id"] for item in folders[key]["songs"]):
        if len(folders[key]["songs"]) >= MAX_TRACKS:
            return await screen(update, "Плейлист заполнен. Выбери другой.", [[Button("← Плейлисты", callback_data="lib:folders")]])
        folders[key]["songs"].append(dict(pending))
        if not any(item["id"] == pending["id"] for item in favorites[uid]):
            favorites[uid].append(dict(pending))
    source = context.user_data.get("new_playlist_move_from")
    if pending and source in folders and source != key:
        folders[source]["songs"] = [item for item in folders[source]["songs"] if item["id"] != pending["id"]]
    await commit(context, uid, store, favorites, folders)
    for field in ("new_collection_song", "new_playlist_move_from", "awaiting_collection_name"):
        context.user_data.pop(field, None)
    await show_playlist(update, context, folders, key)


async def rename_playlist(update, context, store, name):
    folders = await collections(context, update.effective_user.id, store)
    key = context.user_data.get("awaiting_playlist_rename")
    name = clean_name(name)
    if not name or key not in folders:
        context.user_data.pop("awaiting_playlist_rename", None)
        return await show_folders(update, context, store)
    if any(other != key and folder["name"].casefold() == name.casefold() for other, folder in folders.items()):
        return await update.effective_message.reply_text("Такой плейлист уже есть. Выбери другое название.")
    folders[key]["name"] = name
    await save_collections(context, update.effective_user.id, store)
    context.user_data.pop("awaiting_playlist_rename", None)
    await show_playlist(update, context, folders, key)


async def add_picker(update, context, favorites, folders, key, page=0):
    folder = folders.get(key)
    if not folder:
        return
    songs = all_saved(update.effective_user.id, favorites, folders)
    total = max(1, (len(songs) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total - 1))
    identifiers = {song["id"] for song in folder["songs"]}
    rows = [[Button(("✓ " if song["id"] in identifiers else "＋ ") + f"{song['title']} — {song['artist']}"[:50],
                    callback_data=f"lib:mark:{key}:{song['id']}:{page}")]
            for song in songs[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]]
    nav = []
    if page:
        nav.append(Button("←", callback_data=f"lib:add:{key}:{page - 1}"))
    if page + 1 < total:
        nav.append(Button("→", callback_data=f"lib:add:{key}:{page + 1}"))
    if nav:
        rows.append(nav)
    rows += [[Button("✓ Готово", callback_data="lib:col:" + key, style="success")],
             [Button("🔎 Найти ещё музыку", callback_data="ui:search")]]
    await screen(update, f"🎧 <b>{escape(folder['name'])}</b>\nОтметь треки · выбрано {len(folder['songs'])}", rows)


async def handle_library(update, context, favorites, persist_favorites, store, results, send_song, request_download):
    query = update.callback_query
    await query.answer()
    uid, data = update.effective_user.id, query.data or ""
    if len(data.encode()) > 64:
        return
    folders = await collections(context, uid, store)
    if not data.startswith("lib:rename:"):
        context.user_data.pop("awaiting_playlist_rename", None)
    if not data.startswith(("lib:new", "lib:movenew:")):
        for field in ("awaiting_collection_name", "new_collection_song", "new_playlist_move_from"):
            context.user_data.pop(field, None)
    if data == "lib:home":
        return await show_library_home(update, context, favorites, store)
    if data == "lib:folders":
        for field in ("awaiting_collection_name", "new_collection_song", "new_playlist_move_from", "awaiting_playlist_rename"):
            context.user_data.pop(field, None)
        return await show_folders(update, context, store)
    match = re.fullmatch(r"lib:new(?::(-?[0-9]{1,19}))?", data)
    if match:
        context.user_data.pop("new_collection_song", None)
        context.user_data.pop("new_playlist_move_from", None)
        if match[1]:
            song = find_song(uid, int(match[1]), favorites, folders, results)
            if not song:
                return
            context.user_data["new_collection_song"] = dict(song)
        context.user_data["awaiting_collection_name"] = True
        return await screen(update, "🎧 <b>Название нового плейлиста?</b>", [[Button("Отмена", callback_data="lib:folders")]])
    match = re.fullmatch(r"lib:uploads:([0-9]{1,4})", data)
    if match:
        return await show_favorites(update, context, favorites, int(match[1]), uploads_only=True)
    match = re.fullmatch(r"lib:page:([0-9]{1,4})", data)
    if match:
        return await show_favorites(update, context, favorites, int(match[1]))
    match = re.fullmatch(r"lib:col:([0-9a-f]{8})(?::([0-9]{1,3}))?", data)
    if match:
        return await show_playlist(update, context, folders, match[1], int(match[2] or 0))
    match = re.fullmatch(r"lib:(settings|rename|drop|confirmdrop):([0-9a-f]{8})", data)
    if match:
        action, key = match.groups()
        folder = folders.get(key)
        if not folder:
            return await show_folders(update, context, store)
        if action == "settings":
            return await screen(update, f"🎧 <b>{escape(folder['name'])}</b>", [
                [Button("✏ Переименовать", callback_data="lib:rename:" + key)],
                [Button("Удалить плейлист", callback_data="lib:drop:" + key, style="danger")],
                [Button("← К трекам", callback_data="lib:col:" + key)]])
        if action == "rename":
            context.user_data["awaiting_playlist_rename"] = key
            return await screen(update, "Новое название?", [[Button("Отмена", callback_data="lib:col:" + key)]])
        if action == "drop":
            return await screen(update, f"Удалить <b>{escape(folder['name'])}</b>?\nТреки останутся в сохранённых.", [
                [Button("Удалить", callback_data="lib:confirmdrop:" + key, style="danger"), Button("Отмена", callback_data="lib:col:" + key)]])
        favorites[uid] = all_saved(uid, favorites, folders)
        folders.pop(key)
        await commit(context, uid, store, favorites, folders)
        return await show_folders(update, context, store)
    match = re.fullmatch(r"lib:add:([0-9a-f]{8}):([0-9]{1,3})", data)
    if match:
        return await add_picker(update, context, favorites, folders, match[1], int(match[2]))
    match = re.fullmatch(r"lib:mark:([0-9a-f]{8}):(-?[0-9]{1,19}):([0-9]{1,3})", data)
    if match:
        key, identifier, page = match.groups()
        folder, song = folders.get(key), find_song(uid, int(identifier), favorites, folders, results)
        if not folder or not song:
            return
        favorites[uid] = all_saved(uid, favorites, folders)
        if any(item["id"] == song["id"] for item in folder["songs"]):
            folder["songs"] = [item for item in folder["songs"] if item["id"] != song["id"]]
        elif len(folder["songs"]) < MAX_TRACKS:
            folder["songs"].append(dict(song))
        else:
            return await screen(update, "В плейлисте уже 60 треков.", [[Button("← Плейлист", callback_data="lib:col:" + key)]])
        await commit(context, uid, store, favorites, folders)
        return await add_picker(update, context, favorites, folders, key, int(page))
    match = re.fullmatch(r"lib:movenew:([0-9a-f]{8}):(-?[0-9]{1,19})", data)
    if match:
        key, identifier = match.groups()
        folder = folders.get(key)
        song = next((song for song in folder["songs"] if song["id"] == int(identifier)), None) if folder else None
        if not song:
            return
        context.user_data["new_collection_song"] = dict(song)
        context.user_data["new_playlist_move_from"] = key
        context.user_data["awaiting_collection_name"] = True
        return await screen(update, "Название нового плейлиста?", [[Button("Отмена", callback_data="lib:col:" + key)]])
    match = re.fullmatch(r"lib:mv:([0-9a-f]{8}):([0-9a-f]{8}):(-?[0-9]{1,19})", data)
    if match:
        source, target, identifier = match.groups()
        if source not in folders or target not in folders or source == target:
            return
        song = next((song for song in folders[source]["songs"] if song["id"] == int(identifier)), None)
        if not song:
            return
        if not any(item["id"] == song["id"] for item in folders[target]["songs"]):
            if len(folders[target]["songs"]) >= MAX_TRACKS:
                return await screen(update, "Плейлист заполнен.", [[Button("← Назад", callback_data="lib:col:" + source)]])
            folders[target]["songs"].append(dict(song))
        folders[source]["songs"] = [item for item in folders[source]["songs"] if item["id"] != song["id"]]
        favorites[uid] = all_saved(uid, favorites, folders)
        await commit(context, uid, store, favorites, folders)
        return await show_playlist(update, context, folders, target, notice="Перемещено")
    match = re.fullmatch(r"lib:(save|ci|cd|move):([0-9a-f]{8}):(-?[0-9]{1,19})", data)
    if match:
        action, key, identifier = match.groups()
        folder = folders.get(key)
        song = find_song(uid, int(identifier), favorites, folders, results)
        if not folder or not song:
            return await screen(update, "Трек больше недоступен.", [[Button("← Моя музыка", callback_data="lib:home")]])
        if action in ("ci", "cd", "move") and not any(item["id"] == song["id"] for item in folder["songs"]):
            return await show_playlist(update, context, folders, key)
        if action == "save":
            exists = any(item["id"] == song["id"] for item in folder["songs"])
            if not exists and len(folder["songs"]) >= MAX_TRACKS:
                return await screen(update, "Плейлист заполнен.", [[Button("← Плейлисты", callback_data="lib:folders")]])
            favorites[uid] = all_saved(uid, favorites, folders)
            if not any(item["id"] == song["id"] for item in favorites[uid]):
                favorites[uid].append(dict(song))
            if not exists:
                folder["songs"].append(dict(song))
            await commit(context, uid, store, favorites, folders)
            return await show_playlist(update, context, folders, key, notice="Добавлено")
        if action == "cd":
            favorites[uid] = all_saved(uid, favorites, folders)
            folder["songs"] = [item for item in folder["songs"] if item["id"] != song["id"]]
            await commit(context, uid, store, favorites, folders)
            return await show_playlist(update, context, folders, key, notice="Трек убран")
        if action == "move":
            rows = [[Button(other["name"], callback_data=f"lib:mv:{key}:{target}:{identifier}")]
                    for target, other in folders.items() if target != key]
            rows += [[Button("＋ Новый плейлист", callback_data=f"lib:movenew:{key}:{identifier}", style="success")],
                     [Button("← Назад", callback_data=f"lib:ci:{key}:{identifier}")]]
            return await screen(update, "В какой плейлист переместить?", rows)
        from track_card import show_card
        return await show_card(update, context, song, saved=True, extra_rows=[
            [Button("Переместить", callback_data=f"lib:move:{key}:{identifier}"),
             Button("Убрать из плейлиста", callback_data=f"lib:cd:{key}:{identifier}")],
            [Button("← Плейлист", callback_data="lib:col:" + key)]])
    match = re.fullmatch(r"lib:(item|open|download|delete|confirmdelete|put):(-?[0-9]{1,19})", data)
    if not match:
        return
    action, identifier = match.groups()
    song = find_song(uid, int(identifier), favorites, folders, results)
    if not song:
        return await screen(update, "Трек больше недоступен.", [[Button("← Моя музыка", callback_data="lib:home")]])
    if action == "delete":
        return await screen(update, f"Убрать <b>{escape(song['title'])}</b> из Моей музыки?\nТрек будет убран и из плейлистов.", [
            [Button("Убрать", callback_data=f"lib:confirmdelete:{identifier}", style="danger"),
             Button("Отмена", callback_data=f"lib:item:{identifier}")]])
    if action == "confirmdelete":
        favorites[uid] = [item for item in all_saved(uid, favorites, folders) if item["id"] != song["id"]]
        for folder in folders.values():
            folder["songs"] = [item for item in folder["songs"] if item["id"] != song["id"]]
        await commit(context, uid, store, favorites, folders)
        if song.get("kind") == "upload":
            from uploaded_media import owned_path
            path = owned_path(song.get("_library_audio"), uid)
            if path:
                path.unlink(missing_ok=True)
        return await show_favorites(update, context, favorites, context.user_data.get("library_page", 0))
    if action == "download":
        return await request_download(update, context, dict(song))
    if action == "open":
        results[uid] = [dict(song)]
        return await send_song(update, context, 0)
    if action == "put":
        return await save_song(update, context, song, favorites, store)
    from track_card import show_card
    await show_card(update, context, song, saved=True, extra_rows=[
        [Button("Убрать из Моей музыки", callback_data=f"lib:delete:{identifier}")],
        [Button("← Все сохранённые", callback_data=f"lib:page:{context.user_data.get('library_page', 0)}")]])
