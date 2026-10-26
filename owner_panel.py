"""Persistent owner controls. Telegram identity is checked by the caller and middleware."""
import asyncio
import sqlite3
import time
from contextlib import closing
from telegram import InlineKeyboardButton as Button
from ui_layout import comfortable_keyboard as Markup
from operations import _active

FEATURES = {"search": "Поиск", "downloads": "Скачивание", "studio": "Студия", "voice": "Голосовой поиск"}


class Controls:
    def __init__(self, store):
        self.store = store
        self.started = time.monotonic()
        self.settings = {"maintenance": False, "features": dict.fromkeys(FEATURES, True), "blocked": []}
        self.lock = asyncio.Lock()

    async def load(self):
        saved = (await asyncio.to_thread(self.store.load_named, "owner_controls")).get(0, {})
        if isinstance(saved, dict):
            self.settings["maintenance"] = saved.get("maintenance") is True
            enabled = saved.get("features", {})
            if isinstance(enabled, dict):
                self.settings["features"].update({key: enabled[key] for key in FEATURES if type(enabled.get(key)) is bool})
            blocked = saved.get("blocked", [])
            if isinstance(blocked, list):
                self.settings["blocked"] = [uid for uid in blocked if type(uid) is int and uid > 0]

    async def change(self, action, value=None):
        async with self.lock:
            if action == "maintenance":
                self.settings["maintenance"] = not self.settings["maintenance"]
            elif action in FEATURES:
                self.settings["features"][action] = not self.settings["features"][action]
            elif action == "block" and value not in self.settings["blocked"]:
                self.settings["blocked"].append(value)
            elif action == "unblock":
                self.settings["blocked"] = [uid for uid in self.settings["blocked"] if uid != value]
            await asyncio.to_thread(self.store.save_named, "owner_controls", 0, self.settings)

    def enabled(self, feature):
        return self.settings["features"].get(feature, True)

    async def admit(self, handler, update, context):
        if context.application.bot_data["is_owner"](update):
            return True
        uid = update.effective_user.id
        if uid in self.settings["blocked"]:
            await update.effective_message.reply_text("Доступ ограничен.")
            return False
        if self.settings["maintenance"]:
            await update.effective_message.reply_text("🔧 Перерыв на обновление. Попробуй немного позже.")
            return False
        name = handler.__name__
        data = getattr(getattr(update, "callback_query", None), "data", "") or ""
        feature = None
        if name in ("route_music_links", "batch_callback", "download_callback", "download_command", "versions_callback") or data.startswith(("download_", "enhance_", "lib:download:", "track:listen:")) or data == "recognized_download":
            feature = "downloads"
        elif name in ("quick_callback", "studio_callback", "studio_command", "trim_command", "presets_command", "preset_callback") or data.startswith(("effect_", "toggle_", "fx:", "upload:studio:", "track:studio:")) or data in ("apply_effects", "reverse_audio", "make_loop", "detect_chords", "pitch_detect"):
            feature = "studio"
        elif name == "voice_callback" and data == "voice_effects":
            feature = "studio"
        elif name in ("voice_menu", "voice_callback"):
            feature = "voice"
        elif name in ("search_command", "search_result_callback"):
            feature = "search"
        elif name == "handle_message":
            if context.user_data.get("awaiting_catalog"):
                feature = "downloads"
            elif context.user_data.get("awaiting_ringtone") or context.user_data.get("awaiting_trim") or context.user_data.get("awaiting_pitch"):
                feature = "studio"
            elif not context.user_data.get("awaiting_collection_name") and not context.user_data.get("awaiting_playlist_rename"):
                feature = "search"
        if feature and not self.enabled(feature):
            await update.effective_message.reply_text("Этот раздел временно закрыт.")
            return False
        return True


async def show_panel(update, context):
    controls = context.application.bot_data["controls"]
    state = "включён" if controls.settings["maintenance"] else "выключен"
    await update.effective_message.reply_text("⚙ Владелец", reply_markup=Markup([
        [Button("📊 Статистика", callback_data="owner:stats"), Button("🎛 Функции", callback_data="owner:features")],
        [Button("👥 Доступ", callback_data="owner:access"), Button("📢 Рассылка", callback_data="owner:broadcast")],
        [Button("🔧 Обслуживание: " + state, callback_data="owner:maintenance")],
        [Button("Остановить все задачи", callback_data="owner:stopjobs")],
        [Button("🧹 Временные файлы", callback_data="owner:cleanup"), Button("← Меню", callback_data="ui:home")],
    ]))


def user_count(path):
    with closing(sqlite3.connect(path)) as db:
        return db.execute("SELECT COUNT(*) FROM users").fetchone()[0]


async def handle_panel(update, context, owner_ids, users_path, broadcast, cleanup):
    await update.callback_query.answer()
    controls = context.application.bot_data["controls"]
    action = update.callback_query.data
    back = Markup([[Button("← Панель", callback_data="owner:home")]])
    if action == "owner:home":
        return await show_panel(update, context)
    if action == "owner:stats":
        count = await asyncio.to_thread(user_count, users_path)
        minutes = int((time.monotonic() - controls.started) // 60)
        return await update.effective_message.reply_text(
            f"📊 Пользователей: {count}\nАктивных задач: {len(_active)}\nРаботает: {minutes} мин",
            reply_markup=back)
    if action == "owner:maintenance":
        await controls.change("maintenance")
        return await show_panel(update, context)
    if action.startswith("owner:toggle:"):
        feature = action.rsplit(":", 1)[-1]
        if feature in FEATURES:
            await controls.change(feature)
        action = "owner:features"
    if action == "owner:features":
        rows = [[Button(("✓ " if controls.enabled(key) else "○ ") + name, callback_data="owner:toggle:" + key)] for key, name in FEATURES.items()]
        rows.append([Button("← Панель", callback_data="owner:home")])
        return await update.effective_message.reply_text("Доступные разделы", reply_markup=Markup(rows))
    if action == "owner:access":
        return await update.effective_message.reply_text(
            f"👥 Заблокировано: {len(controls.settings['blocked'])}", reply_markup=Markup([
                [Button("Заблокировать", callback_data="owner:block"), Button("Разблокировать", callback_data="owner:unblock")],
                [Button("← Панель", callback_data="owner:home")]]))
    if action in ("owner:block", "owner:unblock"):
        context.user_data["awaiting_owner_action"] = action.split(":")[-1]
        return await update.effective_message.reply_text("Telegram user ID?")
    if action == "owner:stopjobs":
        count = 0
        for op in list(_active.values()):
            op.stopped.set()
            count += 1
        return await update.effective_message.reply_text(f"Останавливаю задач: {count}", reply_markup=back)
    if action == "owner:broadcast":
        return await broadcast(update, context)
    if action == "owner:cleanup":
        return await cleanup(update, context)


async def accept_owner_input(update, context, owner_ids):
    action = context.user_data.get("awaiting_owner_action")
    text = (update.effective_message.text or "").strip()
    if not text.isascii() or not text.isdecimal() or not 0 < int(text) < 10**16:
        return await update.effective_message.reply_text("Нужен числовой Telegram user ID. /cancel — отмена.")
    uid = int(text)
    if uid in owner_ids:
        return await update.effective_message.reply_text("Владельца нельзя заблокировать.")
    await context.application.bot_data["controls"].change(action, uid)
    context.user_data.pop("awaiting_owner_action", None)
    await update.effective_message.reply_text("✓ Сохранено.")
    await show_panel(update, context)
