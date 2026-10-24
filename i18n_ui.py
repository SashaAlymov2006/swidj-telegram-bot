"""Offline UI localization at the Telegram boundary. User media and identifiers stay unchanged."""
import contextvars
import functools
import json
import re
from pathlib import Path
from telegram.ext import ExtBot

locale = contextvars.ContextVar("swidj_locale", default="ru")
action = contextvars.ContextVar("swidj_ui_action", default="")
CATALOG = json.loads(Path(__file__).with_name("i18n_en.json").read_text(encoding="utf-8"))
keys = sorted(CATALOG, key=len, reverse=True)
def boundary(key):
    return (r"(?<!\w)" if key[0].isalnum() else "") + re.escape(key) + (r"(?!\w)" if key[-1].isalnum() else "")
PATTERN = re.compile("|".join(boundary(key) for key in keys))

def english(text, *, protect=True):
    if not isinstance(text,str):
        return text
    held=[]
    def keep(value):
        held.append(value)
        return "\ufff0"+str(len(held)-1)+"\ufff1"
    if protect:
        # Titles, artists, user playlists and transcribed lyrics are content, not UI.
        def media_content(m):
            ui = ("🎵 <b>Здесь будут твои треки</b>", "🎵 <b>Очередь ·",
                  "🔔 <b>Рингтон</b>", "🔔 <b>С какого момента?</b>")
            return m[0] if m[0].startswith(ui) else keep(m[0])
        text=re.sub(r"(?:🎵|🔔) <b>.*?</b>\n[^\n]*",media_content,text,flags=re.S)
        text=re.sub(r"(✅ Распознано:\n)(.*)",lambda m:m[1]+keep(m[2]),text,flags=re.S)
        text=re.sub(r"(🎵 Найдено совпадение: )(.*)",lambda m:m[1]+keep(m[2]),text)
        text=re.sub(r"(📝 )(.*?)(\n\nИскать по этим словам\?)",lambda m:m[1]+keep(m[2])+m[3],text,flags=re.S)
        text=re.sub(r"(✅ <b>Сохранено</b>\n)([^\n]*)",lambda m:m[1]+keep(m[2]),text)
        text=re.sub(r"(🎛 Студия\n)([^\n]*)(?=\nВыбрано:|$)",lambda m:m[1]+keep(m[2]),text)
        text=re.sub(r"((?:Убрать|Удалить) <b>)(.*?)(</b>)",lambda m:m[1]+keep(m[2])+m[3],text,flags=re.S)
        def folder(m):
            return m[0] if m[1] in ("Мои плейлисты","Название нового плейлиста?") else "🎧 <b>"+keep(m[1])+"</b>"
        text=re.sub(r"🎧 <b>(.*?)</b>",folder,text,flags=re.S)
    text=PATTERN.sub(lambda m:CATALOG[m[0]],text)
    text=re.sub(r"\b1 tracks\b","1 track",text)
    text=re.sub(r"\ufff0(\d+)\ufff1",lambda m:held[int(m[1])],text)
    return text

def tr(text):
    return english(text) if locale.get()=="en" else text

def markup(value):
    if hasattr(value,"to_dict"): value=value.to_dict()
    if isinstance(value,str):
        try: value=json.loads(value)
        except ValueError: return value
    if not isinstance(value,dict):return value
    result=dict(value)
    for field in ("inline_keyboard","keyboard"):
        if field not in result:continue
        rows=[]
        for row in result[field]:
            buttons=[]
            for original in row:
                button=original.to_dict() if hasattr(original,"to_dict") else dict(original) if isinstance(original,dict) else original
                if isinstance(button,dict) and isinstance(button.get("text"),str):
                    button=dict(button)
                    callback=button.get("callback_data","")
                    dynamic=callback.startswith(("ver:pick:","lib:item:","lib:ci:","lib:col:","lib:save:","lib:mv:","lib:mark:"))
                    retry = callback.startswith("ver:pick:") and button["text"] == "🔄 Повторить"
                    if (not dynamic or retry) and not callback.startswith("lang:"):
                        button["text"]=english(button["text"],protect=False)
                buttons.append(button)
            rows.append(buttons)
        result[field]=rows
    if isinstance(result.get("input_field_placeholder"),str):
        result["input_field_placeholder"]=english(result["input_field_placeholder"])
    return result

def localized_data(endpoint,data):
    if locale.get()!="en":return data
    result=dict(data)
    current=action.get()
    literal=current=="admin_send" and not str(result.get("text","")).startswith("📤 Разослано")
    lyrics=current.startswith("lyrics_") and result.get("text") not in (
        "⏳ Загружаю текст песни...","Не удалось получить текст песни.","Ошибка при получении текста песни.")
    if not literal and not lyrics:
        for field in ("text","caption"):
            if isinstance(result.get(field),str):result[field]=english(result[field])
        media=result.get("media")
        if hasattr(media,"to_dict"):media=media.to_dict()
        if isinstance(media,dict) and isinstance(media.get("caption"),str):
            result["media"]=dict(media,caption=english(media["caption"]))
    if "reply_markup" in result:result["reply_markup"]=markup(result["reply_markup"])
    return result

class LocalizedBot(ExtBot):
    async def _do_post(self,endpoint,data,**kwargs):
        return await super()._do_post(endpoint,localized_data(endpoint,data),**kwargs)

def localized_callback(handler):
    @functools.wraps(handler)
    async def wrapped(update,context):
        marker=locale.set(context.user_data.get("language","ru"))
        tag=action.set(getattr(getattr(update,"callback_query",None),"data",None) or handler.__name__)
        try:return await handler(update,context)
        finally:
            action.reset(tag);locale.reset(marker)
    return wrapped
