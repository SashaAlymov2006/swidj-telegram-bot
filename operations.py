"""Cooperative cancellation without abandoning running worker cleanup."""
import asyncio
from contextvars import ContextVar
from dataclasses import dataclass, field
import secrets
import subprocess
import threading
import time
from telegram import InlineKeyboardButton as Button, InlineKeyboardMarkup as Markup

_current = ContextVar("swidj_operation", default=None)
_active = {}


class OperationCancelled(BaseException):
    pass


@dataclass
class Operation:
    uid: int
    token: str = field(default_factory=lambda: secrets.token_hex(6))
    stopped: threading.Event = field(default_factory=threading.Event)
    message: object = None


def checkpoint():
    op = _current.get()
    if op and op.stopped.is_set():
        raise OperationCancelled()


def cancel(uid, token=None):
    op = _active.get(uid)
    if not op or (token is not None and token != op.token):
        return False
    op.stopped.set()
    return True


def stop_keyboard(op):
    return Markup([[Button("✕ Отменить", callback_data="op:cancel:" + op.token)]])


async def stage(text):
    checkpoint()
    op = _current.get()
    if op and op.message:
        try:
            await op.message.edit_text(text, reply_markup=stop_keyboard(op))
        except Exception:
            pass
    checkpoint()


def needed(handler, update):
    name = handler.__name__
    data = getattr(getattr(update, "callback_query", None), "data", "") or ""
    if name=='track_callback' and data.startswith('track:lyrics:'):
        return 'Ищу текст…'
    if name=='preset_callback' and data.startswith('preset:apply:'):
        return 'Обрабатываю…'
    if name in ("download_callback", "download_command", "trim_command", "versions_callback", "upload_callback"):
        return "Готовлю…"
    if name in ("route_music_links", "batch_callback"):
        return "Готовлю очередь…" if name == "batch_callback" else "Читаю ссылки…"
    if name == "handle_message" and (getattr(getattr(update, "effective_message", None), "text", "") or "").strip():
        return "Ищу…"
    if name == "track_callback" and data.startswith(("track:listen:", "track:studio:", "track:save:", "track:playlist:")):
        return "Готовлю…"
    if name == "library_callback" and data.startswith("lib:download:"):
        return "Ищу версии…"
    if name == "voice_callback" and data != "voice_effects":
        return "Слушаю…"
    if name == "quick_callback" and data.startswith(("quick:preset:", "quick:export:", "quick:ringtone")):
        return "Готовлю…"
    if name == "studio_callback" and data in ("studio:mp3", "studio:wav", "studio:preview", "studio:info"):
        return "Обрабатываю…"
    if name == "handle_callback" and (data.startswith(("download_", "enhance_", "lyrics_", "fx:")) or data in (
            "recognized_download", "apply_effects", "make_loop", "reverse_audio", "detect_chords")):
        return "Готовлю…"
    return None


async def run_handler(handler, update, context):
    text = needed(handler, update)
    if handler.__name__ == "handle_message" and any(context.user_data.get(key) for key in (
            "awaiting_collection_name", "awaiting_playlist_rename", "awaiting_owner_action", "awaiting_broadcast_text")):
        text = None
    if handler.__name__ == "handle_message" and context.user_data.get("awaiting_ringtone"):
        text = None
    if not text or not getattr(update, "effective_message", None):
        return await handler(update, context)
    op = Operation(update.effective_user.id)
    _active[op.uid] = op
    marker = _current.set(op)
    try:
        op.message = await update.effective_message.reply_text(text, reply_markup=stop_keyboard(op))
        result = await handler(update, context)
        checkpoint()
        if op.message:
            try:
                await op.message.delete()
            except Exception:
                pass
        return result
    except OperationCancelled:
        if op.message:
            try:
                await op.message.edit_text("Отменено.")
            except Exception:
                pass
    except Exception:
        if op.message:
            try:
                await op.message.delete()
            except Exception:
                pass
        raise
    finally:
        if _active.get(op.uid) is op:
            _active.pop(op.uid, None)
        _current.reset(marker)


def run_process(command, *, timeout=120, capture_output=True, check=False, **kwargs):
    checkpoint()
    process = subprocess.Popen(command, stdout=subprocess.PIPE if capture_output else None,
                               stderr=subprocess.PIPE if capture_output else None, **kwargs)
    deadline = time.monotonic() + timeout
    try:
        while True:
            checkpoint()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(command, timeout)
            try:
                out, err = process.communicate(timeout=min(0.2, remaining))
                break
            except subprocess.TimeoutExpired:
                continue
        checkpoint()
        result = subprocess.CompletedProcess(command, process.returncode, out, err)
        if check:
            result.check_returncode()
        return result
    except BaseException:
        if process.poll() is None:
            process.terminate()
            try:
                process.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
        raise


async def cancel_callback(update, context):
    token = update.callback_query.data.rsplit(":", 1)[-1]
    if cancel(update.effective_user.id, token):
        for queue in context.user_data.get("link_queues", {}).values():
            if queue.get("op_token") == token:
                queue["stopped"] = True
        await update.callback_query.answer("Отменяю…")
    else:
        await update.callback_query.answer("Задача уже завершена.")
