from i18n_ui import tr
"""Audio studio navigation and local tool handlers."""
import asyncio
import os
import tempfile
from html import escape
from telegram import InlineKeyboardButton as Button
from ui_layout import comfortable_keyboard as Markup
from scratch import scratch_root
from operations import checkpoint, stage
from studio_tools import audio_info, timestamp, export_audio

GROUPS = {
    "level": ("Громкость и чистота", ("normalize", "compressor", "mastering")),
    "tone": ("Тон и скорость", ("pitch_up", "pitch_down", "speed_up", "slow_down")),
    "color": ("Бас и стиль", ("bass_boost", "equalizer", "highpass", "lowpass", "lofi")),
    "space": ("Эхо и пространство", ("reverb", "pro_reverb", "echo", "delay")),
}


def keyboard(effects, selected, song=None, category="main"):
    rows = []
    if category == "bass":
        from audio_tools import BASS_GAINS
        options = [("off", "Без изменения")] + [(key, effects[key]) for key in BASS_GAINS]
        active = next((key for key in selected if key in BASS_GAINS), "off")
        rows = [[Button(("✓ " if active == key else "") + title,
                        callback_data="studio:bass:" + key)] for key, title in options]
        rows.append([Button("← Студия", callback_data="studio:home")])
    elif category in GROUPS:
        rows = [[Button(("✓ " if key in selected else "") + ("Регулировка баса" if key == "bass_boost" else effects[key]), callback_data="studio:bass" if key == "bass_boost" else "toggle_" + key)]
                for key in GROUPS[category][1]]
        rows.append([Button("← Студия", callback_data="studio:home")])
    else:
        groups = [Button(title, callback_data="studio:group:" + key) for key, (title, _) in GROUPS.items()]
        rows = [[Button("✨ Ремикс и рингтон", callback_data="quick:home", style="primary")], groups[:2], groups[2:]]
        rows += [
            [Button("✂ Обрезать", callback_data="studio:trim"), Button("🔄 Изменить формат", callback_data="studio:formats")],
            [Button("Ещё инструменты", callback_data="studio:more")],
        ]
        if song:
            rows.append([Button("＋ Сохранить", callback_data=f"upload:save:{song['id']}" if song.get("kind") == "upload" else "audio_favorite", style="success")])
    if selected:
        rows += [[Button(f"▶ Послушать · {len(selected)} эфф.", callback_data="fx:preview")],
                 [Button("Снять выбор", callback_data="studio:reset")]]
    rows += [[Button("← Меню", callback_data="ui:home"), Button("?", callback_data="studio:help")]]
    return Markup(rows)


async def show_studio(update, context, effects):
    source = context.user_data.get("last_audio_path")
    if not source or not os.path.isfile(source):
        return await update.effective_message.reply_text("🎛 Пришли аудиофайл — затем появятся инструменты студии.")
    selected = context.user_data.get("pending_effects", [])
    names = ", ".join(effects.get(key, key) for key in selected) or "ничего"
    context.user_data["studio_category"] = "main"
    await update.effective_message.reply_text(
        "🎛 Студия" + ("\n" + str(context.user_data.get("downloaded_song", {}).get("title", ""))[:70] if context.user_data.get("downloaded_song") else "") + (f"\nВыбрано: {names}" if selected else ""),
        reply_markup=keyboard(effects, selected, context.user_data.get("downloaded_song")))


async def deliver_export(update, context, *, format="mp3", start=0, end=None, label="Аудио"):
    source = context.user_data.get("last_audio_path")
    if not source or not os.path.isfile(source):
        return await update.effective_message.reply_text("Сначала пришли аудиофайл.")
    await stage("Готовлю файл…")
    try:
        with tempfile.TemporaryDirectory(dir=scratch_root(), prefix="swidj_export_") as directory:
            output = os.path.join(directory, "SwiDJ." + format)
            duration = await asyncio.to_thread(export_audio, source, output, start=start, end=end, format=format)
            checkpoint()
            from audio_presentation import music_labels, send_music
            song = context.user_data.get("downloaded_song") or {}
            title = song.get("title") or "Мой трек"
            if label != "Аудио":
                title = f"{title} · {tr(label)}"
            title, artist, filename = music_labels(title, song.get("artist"))
            if format == "wav":
                size = os.path.getsize(output) / 1024**2
                with open(output, "rb") as audio:
                    await update.effective_message.reply_document(
                        audio, filename=filename[:-4] + ".wav",
                        caption=f"🎵 <b>{escape(title)}</b>\n{escape(artist)}\n\nWAV · {size:.1f} МБ",
                        parse_mode="HTML")
            else:
                await send_music(context.bot, update.effective_chat.id, output, title, artist, song.get("cover"))


    except ValueError as exc:
        await update.effective_message.reply_text(str(exc))


async def trim_command(update, context):
    if len(context.args) != 2:
        return await update.effective_message.reply_text(
            "✂ Укажи начало и конец: /trim 0:10 0:30\nМожно в секундах: /trim 10 30. Исходник сохраняется.")
    try:
        start, end = (timestamp(value) for value in context.args)
        if end - start > 600:
            raise ValueError("Для обрезки выбери фрагмент не длиннее 10 минут.")
        context.user_data.pop("awaiting_trim", None)
        await deliver_export(update, context, start=start, end=end, label="Фрагмент")
    except ValueError as exc:
        await update.effective_message.reply_text(str(exc))


async def handle_studio(update, context, effects, action_override=None):
    await update.callback_query.answer()
    action = action_override or update.callback_query.data
    context.user_data.pop("awaiting_ringtone", None)
    if action != "studio:trim":
        context.user_data.pop("awaiting_trim", None)
    if action == "studio:bass" or action.startswith("studio:bass:"):
        source = context.user_data.get("last_audio_path")
        if not source or not os.path.isfile(source):
            return await update.effective_message.reply_text("Сначала пришли аудиофайл.")
        from audio_tools import BASS_GAINS
        selected = list(context.user_data.get("pending_effects", []))
        if action.startswith("studio:bass:"):
            choice = action.rsplit(":", 1)[-1]
            if choice not in BASS_GAINS and choice != "off":
                return
            selected = [key for key in selected if key not in BASS_GAINS]
            if choice != "off":
                selected.append(choice)
            context.user_data["pending_effects"] = selected
            context.user_data.pop("effect_preview", None)
        context.user_data["studio_category"] = "bass"
        return await update.callback_query.edit_message_text(
            "🎚 Регулировка баса\nВыбери уровень → послушай пример → примени к треку.",
            reply_markup=keyboard(effects, selected, context.user_data.get("downloaded_song"), "bass"))
    if action in ("studio:home", "studio:reset"):
        if action == "studio:reset":
            context.user_data["pending_effects"] = []
        return await show_studio(update, context, effects)
    if action == "studio:help":
        return await update.effective_message.reply_text(
            "Выбери эффекты → послушай пример → примени к треку.\n"
            "Инструменты работают с исходным аудио. Результаты приходят отдельными файлами.",
            reply_markup=Markup([[Button("← Студия", callback_data="studio:home")]]))
    if action == "studio:formats":
        return await update.effective_message.reply_text(
            "🔄 <b>Формат аудио</b>\n\n"
            "<b>MP3</b> — компактный файл для прослушивания и отправки.\n"
            "<b>WAV</b> — без сжатия, для работы со звуком. Занимает больше места.",
            parse_mode="HTML", reply_markup=Markup([
                [Button("MP3 · компактный файл", callback_data="studio:mp3", style="primary")],
                [Button("WAV · без сжатия", callback_data="studio:wav")],
                [Button("← Студия", callback_data="studio:home")]]))
    if action == "studio:more":
        return await update.effective_message.reply_text("Инструменты", reply_markup=Markup([
            [Button("ℹ Об аудио", callback_data="studio:info")],
            [Button("🎹 Сдвиг тона", callback_data="pitch_detect"), Button("🔄 Реверс", callback_data="reverse_audio")],
            [Button("🔂 Луп", callback_data="make_loop"), Button("🎼 Анализ", callback_data="detect_chords")],
            [Button("📝 Найти по словам", callback_data="audio_recognize")],
            [Button("← Студия", callback_data="studio:home")]]))
    if action.startswith("studio:group:"):
        category = action.rsplit(":", 1)[-1]
        if category not in GROUPS:
            return
        context.user_data["studio_category"] = category
        return await update.effective_message.reply_text(
            "🎛 Аудиостудия → " + GROUPS[category][0] + "",
            reply_markup=keyboard(effects, context.user_data.get("pending_effects", []),
                                  context.user_data.get("downloaded_song"), category))
    if action == "studio:trim":
        context.user_data["awaiting_trim"] = True
        return await update.effective_message.reply_text("✂ Начало и конец? Например: 0:10 0:30")

    source = context.user_data.get("last_audio_path")
    if not source or not os.path.isfile(source):
        return await update.effective_message.reply_text("Сначала пришли аудиофайл.")
    if action == "studio:info":
        try:
            info = await asyncio.to_thread(audio_info, source)
            seconds = round(info["duration"])
            await update.effective_message.reply_text(
                f"ℹ Исходный файл\nДлительность: {seconds // 60}:{seconds % 60:02d}\n"
                f"Кодек: {info['codec']}\nЧастота: {info['sample_rate']} Гц\n"
                f"Каналы: {info['channels']}\nРазмер: {info['size'] / 1024**2:.2f} МБ")
        except ValueError as exc:
            await update.effective_message.reply_text(str(exc))
        return
    if action == "studio:preview":
        try:
            info = await asyncio.to_thread(audio_info, source)
            return await deliver_export(update, context, end=min(30, info["duration"]), label="Фрагмент до 30 секунд")
        except ValueError as exc:
            return await update.effective_message.reply_text(str(exc))
    if action in ("studio:mp3", "studio:wav"):
        return await deliver_export(update, context, format=action.split(":")[-1], label="Аудио")
