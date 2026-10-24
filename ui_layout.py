"""Readable full-width choices; keep paging and track controls compact."""
from telegram import InlineKeyboardMarkup as TelegramMarkup

def comfortable_keyboard(rows, **kwargs):
    result = []
    for original in rows:
        row = list(original)
        navigation = all(str(button.callback_data or "").startswith(("lib:page:", "lib:uploads:", "ui:home")) or button.text.startswith(("←", "Дальше")) for button in row)
        if len(row) == 2 and not navigation:
            result.extend([[button] for button in row])
        else:
            result.append(row)
    return TelegramMarkup(result, **kwargs)
