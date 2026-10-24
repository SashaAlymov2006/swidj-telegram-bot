from i18n_ui import tr
"""Local remix presets and a short ringtone from a chosen moment."""
import asyncio
import os
import re
import secrets
import tempfile
from html import escape
from telegram import InlineKeyboardButton as Button
from ui_layout import comfortable_keyboard as Markup
from studio_tools import audio_info, timestamp, export_audio
from scratch import scratch_root
from operations import checkpoint, stage

PRESETS = {
    "speed": ("Ускоренный", ("speed_up", "normalize")),
    "slow": ("Замедленный с эхом", ("slow_down", "reverb", "normalize")),
    "bass": ("Больше баса", ("bass_boost", "normalize")),
}

def valid_source(context, request):
    source = request.get("source")
    return source and source == context.user_data.get("last_audio_path") and os.path.isfile(source)

async def formats(update, token, request):
    start = request.get("start", 0)
    length = min(30, request["duration"] - start)
    await update.effective_message.reply_text(
        f"🔔 <b>Рингтон</b>\nС {int(start)//60}:{int(start)%60:02d} · до {length:.0f} сек.\n\nВыбери формат файла:",
        parse_mode="HTML", reply_markup=Markup([
            [Button("MP3", callback_data=f"quick:export:{token}:mp3", style="primary")],
            [Button("M4R · для iPhone", callback_data=f"quick:export:{token}:m4r")],
            [Button("← Студия", callback_data="studio:home")]]))

async def accept_time(update, context, text):
    token = context.user_data.get("awaiting_ringtone")
    request = context.user_data.get("ringtone_requests", {}).get(token)
    if not request or not valid_source(context, request):
        context.user_data.pop("awaiting_ringtone", None)
        return await update.effective_message.reply_text("Аудио изменилось. Открой создание рингтона ещё раз.")
    try:
        start = timestamp(text.strip())
        if start >= request["duration"]:
            raise ValueError("Выбери момент в пределах длительности трека.")
    except ValueError as exc:
        return await update.effective_message.reply_text(str(exc))
    request["start"] = start
    context.user_data.pop("awaiting_ringtone", None)
    await formats(update, token, request)

async def handle_quick(update, context):
    await update.callback_query.answer()
    data = update.callback_query.data
    context.user_data.pop("awaiting_trim", None)
    context.user_data.pop("awaiting_ringtone", None)
    source = context.user_data.get("last_audio_path")
    if not source or not os.path.isfile(source):
        return await update.effective_message.reply_text("Сначала пришли аудио или скачай трек.")
    if data == "quick:home":
        return await update.effective_message.reply_text("✨ <b>Ремикс и рингтон</b>\nВыбери готовый вариант:", parse_mode="HTML",
            reply_markup=Markup([[Button(name, callback_data="quick:preset:"+key)] for key,(name,_) in PRESETS.items()] + [
                [Button("🔔 Сделать рингтон", callback_data="quick:ringtone")],
                [Button("← Студия", callback_data="studio:home")]]))
    if data == "quick:preset:bass":
        context.user_data["pending_effects"] = []
        context.user_data.pop("effect_preview", None)
        from studio_ui import handle_studio
        from bass_labels import BASS_LABELS
        return await handle_studio(update, context, BASS_LABELS, action_override="studio:bass")
    if data.startswith("quick:preset:"):
        preset = PRESETS.get(data.rsplit(":",1)[-1])
        if not preset:
            return
        context.user_data["pending_effects"] = list(preset[1])
        from effect_preview import preview_effects
        return await preview_effects(update, context)
    if data == "quick:ringtone":
        info = await asyncio.to_thread(audio_info, source)
        token = secrets.token_hex(5)
        requests = context.user_data.setdefault("ringtone_requests", {})
        requests[token] = {"source": source, "duration": info["duration"],
                           "song": dict(context.user_data.get("downloaded_song") or {}), "start":0}
        while len(requests)>8:
            requests.pop(next(iter(requests)))
        return await update.effective_message.reply_text("🔔 <b>С какого момента?</b>\nРингтон — до 30 секунд.", parse_mode="HTML",
            reply_markup=Markup([
                [Button("С начала · 0:00", callback_data=f"quick:start:{token}", style="primary")],
                [Button("Выбрать момент", callback_data=f"quick:time:{token}")],
                [Button("← Студия", callback_data="studio:home")]]))
    match = re.fullmatch(r"quick:(start|time|export):([0-9a-f]{10})(?::(mp3|m4r))?", data or "")
    if not match:
        return
    action, token, kind = match.groups()
    request = context.user_data.get("ringtone_requests", {}).get(token)
    if not request or not valid_source(context, request):
        return await update.effective_message.reply_text("Этот выбор уже недоступен. Открой создание рингтона ещё раз.")
    if action == "time":
        context.user_data["awaiting_ringtone"] = token
        return await update.effective_message.reply_text("Начало рингтона? Например: 0:45",
            reply_markup=Markup([[Button("Отмена", callback_data="studio:home")]]))
    if action == "start":
        request["start"] = 0
        return await formats(update, token, request)
    if action != "export" or kind not in ("mp3","m4r"):
        return
    await stage("Готовлю рингтон…")
    try:
        with tempfile.TemporaryDirectory(dir=scratch_root(),prefix="swidj_ringtone_") as directory:
            output=os.path.join(directory,"ringtone."+kind)
            start=request["start"]
            await asyncio.to_thread(export_audio,source,output,start=start,end=min(start+30,request["duration"]),format=kind)
            checkpoint()
            from audio_presentation import send_music, music_labels
            song=request["song"]
            title=(song.get("title") or "Мой трек")+" · "+tr("Рингтон")
            if kind=="mp3":
                return await send_music(context.bot,update.effective_chat.id,output,title,song.get("artist"),song.get("cover"))
            title,artist,filename=music_labels(title,song.get("artist"))
            with open(output,"rb") as audio:
                return await update.effective_message.reply_document(audio,filename=filename[:-4]+".m4r",
                    caption=f"🔔 <b>{escape(title)}</b>\n{escape(artist)}",parse_mode="HTML")
    except ValueError as exc:
        await update.effective_message.reply_text(str(exc))
