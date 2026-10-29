"""Short track cards, with immutable per-user button snapshots."""
import asyncio
from html import escape
import re
import secrets
import os
from urllib.parse import urlparse, quote, urlsplit, urlunsplit, parse_qsl, urlencode
from telegram import InlineKeyboardButton as Button, InputFile, InputMediaPhoto, WebAppInfo
from telegram.error import TelegramError, BadRequest
from ui_layout import comfortable_keyboard as Markup
from audio_presentation import fetch_cover, clean_label

def card_keyboard(context, song, saved=False, extra_rows=None, *, delivered=False):
    token = secrets.token_hex(5)
    snapshots = context.user_data.setdefault("track_cards", {})
    snapshots[token] = dict(song)
    from search_recovery import remember,lookup
    reference=song.get('_search_page')
    bookmark=lookup(context,reference[0]) if isinstance(reference,(list,tuple)) and reference else None
    remember(context,token,bookmark['query'] if bookmark else song.get('_search_query') or ' '.join(str(song.get(k) or '') for k in ('artist','title')),
             bookmark['mode'] if bookmark else context.user_data.get('search_mode') if song.get('_search_query') else 'title')
    while len(snapshots) > 40:
        snapshots.pop(next(iter(snapshots)))
    def button(text, action, style=None):
        return Button(text, callback_data=f"track:{action}:{token}", style=style)
    rows = [] if delivered else search_navigation(context, song)
    if not delivered:
        rows.append([button("⬇ Скачать трек", "listen", "primary")])
    rows += [[button("✓ Сохранено" if saved else "＋ Сохранить", "save", "success")],
             [button("＋ В плейлист", "playlist")],
             [button("🎛 Обработать", "studio")]]
    if os.getenv('MINIAPP_ENABLED','').lower() in ('1','true') and (getattr(context,'_chat_id',None) is None or context._chat_id>0):
        from miniapp_server import public_url
        base=public_url()
        if base:
            parsed=urlsplit(base);query=dict(parse_qsl(parsed.query));query['track']=str(song['id'])
            url=urlunsplit((parsed.scheme,parsed.netloc,parsed.path,urlencode(query),'studio'))
            label='Studio in app' if context.user_data.get('language')=='en' else 'Студия в приложении'
            rows.append([Button(label,web_app=WebAppInfo(url))])
    if song.get("kind") != "upload":
        rows.append([button("📄 Текст", "lyrics")])
        rows.append([button("О треке / автор", "info")])
    return Markup(rows + list(extra_rows or []))

def search_navigation(context, song):
    reference = song.get("_search_page")
    if not reference or len(reference) != 2:
        return []
    token, index = reference
    songs = context.user_data.get("search_pages", {}).get(token, [])
    rows = []
    if index:
        rows.append([Button("← Предыдущий вариант", callback_data=f"srch:{token}:{index-1}")])
    if index + 1 < len(songs):
        rows.append([Button("Следующий вариант →", callback_data=f"srch:{token}:{index+1}", style="primary")])
    return rows


async def retire_download_menus(update, context, request=None):
    """Only retire bot messages that initiated a successful download, never user messages."""
    chat = getattr(getattr(update, "effective_chat", None), "id", None)
    if type(chat) is not int:
        return
    identifiers = set()
    for entry in (request or {}).get("menu_messages", []):
        if isinstance(entry, (list, tuple)) and len(entry) == 2 and entry[0] == chat and type(entry[1]) is int:
            identifiers.add(entry[1])
    query = getattr(update, "callback_query", None)
    message = getattr(query, "message", None)
    sender = getattr(message, "from_user", None)
    if message and sender and sender.is_bot and type(getattr(message, "message_id", None)) is int:
        identifiers.add(message.message_id)
    for identifier in identifiers:
        try:
            await context.bot.delete_message(update.effective_chat.id, identifier)
        except TelegramError:
            try:
                await context.bot.edit_message_reply_markup(update.effective_chat.id, identifier, reply_markup=None)
            except TelegramError:
                pass


async def show_card(update, context, song, *, saved=False, extra_rows=None, notice=""):
    title = clean_label(song.get("title"), "Мой трек", 180)
    artist = clean_label(song.get("artist"), "Исполнитель не указан", 120)
    query = getattr(update, "callback_query", None)
    message = getattr(query, "message", None)
    delivered = bool(notice and message and (getattr(message, "audio", None) or getattr(message, "voice", None) or getattr(message, "document", None)))
    text = f"🎵 <b>{escape(title)}</b>\n{escape(artist)}"
    reference = song.get("_search_page")
    if reference and not delivered:
        total = len(context.user_data.get("search_pages", {}).get(reference[0], []))
        if total:
            text = f"🔎 Вариант {reference[1]+1} из {total}\n\n" + text
    if notice:
        text += "\n\n" + escape(notice)
    markup = card_keyboard(context, song, saved, extra_rows, delivered=delivered)
    # A save confirmation can update the same card without fetching its cover again.
    if notice and message:
        try:
            if message.photo or delivered:
                return await query.edit_message_caption(caption=text, parse_mode="HTML", reply_markup=markup)
            if message.text:
                return await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=markup,
                                                     disable_web_page_preview=True)
        except TelegramError:
            pass
    cover = await asyncio.to_thread(fetch_cover, song.get("cover")) if song.get("cover") else None
    if message:
        try:
            if cover and (message.photo or message.text):
                return await query.edit_message_media(
                    media=InputMediaPhoto(InputFile(cover, filename="cover.jpg"), caption=text, parse_mode="HTML"),
                    reply_markup=markup)
            if not cover and message.text:
                return await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=markup,
                                                     disable_web_page_preview=True)
        except TelegramError:
            pass
    kwargs = dict(chat_id=update.effective_chat.id, parse_mode="HTML", reply_markup=markup)
    result = None
    if cover:
        try:
            result = await context.bot.send_photo(photo=InputFile(cover, filename="cover.jpg"), caption=text, **kwargs)
        except TelegramError:
            pass
    if result is None:
        result = await context.bot.send_message(text=text, disable_web_page_preview=True, **kwargs)
    if message and (getattr(message, "text", None) or getattr(message, "photo", None)):
        await retire_download_menus(update, context)
    return result

def selected_song(context, data):
    match = re.fullmatch(r"track:(listen|save|playlist|studio|lyrics|info):([0-9a-f]{10})", data or "")
    song = context.user_data.get("track_cards", {}).get(match[2]) if match else None
    return (match[1], dict(song)) if song else (None, None)
