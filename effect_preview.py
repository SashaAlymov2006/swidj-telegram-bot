from i18n_ui import tr
"""Preview selected effects on a short clip before processing the source."""
import asyncio
import os
import secrets
import tempfile
from telegram import InlineKeyboardButton as Button
from ui_layout import comfortable_keyboard as Markup
from audio_tools import effect
from studio_tools import audio_info, export_audio
from scratch import scratch_root
from operations import checkpoint, stage


async def preview_effects(update, context):
    source = context.user_data.get("last_audio_path")
    selected = list(context.user_data.get("pending_effects", []))
    if not source or not os.path.isfile(source):
        return await update.effective_message.reply_text("Пришли аудиофайл.")
    if not selected:
        return await update.effective_message.reply_text("Выбери эффекты.")
    await stage("Готовлю пример…")
    with tempfile.TemporaryDirectory(dir=scratch_root(), prefix="swidj_fx_preview_") as directory:
        info = await asyncio.to_thread(audio_info, source)
        current = os.path.join(directory, "sample.mp3")
        await asyncio.to_thread(export_audio, source, current, end=min(15, info["duration"]))
        for index, name in enumerate(selected):
            await stage(f"Эффекты · {index + 1}/{len(selected)}")
            output = os.path.join(directory, f"effect-{index}.mp3")
            await asyncio.to_thread(effect, current, output, name)
            current = output
        bounded = os.path.join(directory, "preview.mp3")
        processed_info = await asyncio.to_thread(audio_info, current)
        await asyncio.to_thread(export_audio, current, bounded, end=min(15, processed_info["duration"]))
        current = bounded
        checkpoint()
        token = secrets.token_hex(5)
        context.user_data["effect_preview"] = {"token": token, "source": source, "selected": selected}
        with open(current, "rb") as audio:
            await update.effective_message.reply_audio(
                audio, title=tr("Пример эффектов · до 15 секунд"), performer="SwiDJ",
                reply_markup=Markup([
                    [Button("✓ Применить ко всему треку", callback_data="fx:apply:" + token, style="success")],
                    [Button("Изменить эффекты", callback_data="studio:home")]]))


def accept_preview(context, token):
    preview = context.user_data.get("effect_preview")
    if not preview or preview.get("token") != token:
        return False
    if preview["source"] != context.user_data.get("last_audio_path") or preview["selected"] != context.user_data.get("pending_effects", []):
        return False
    context.user_data.pop("effect_preview", None)
    return True
