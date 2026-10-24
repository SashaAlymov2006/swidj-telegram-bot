"""Closed error categories: never put provider messages or credentials in logs."""
def classify_error(error):
    if type(error).__name__ != 'BadRequest':
        return 'unexpected'
    message = str(error).lower()
    categories = (
        (('query is too old', 'query id is invalid', 'response timeout expired'), 'callback_expired'),
        (("can't parse entities", 'cannot parse entities', 'unsupported start tag'), 'telegram_text_format'),
        (('message is not modified',), 'message_unchanged'),
        (('file is too big', 'request entity too large', 'file too large'), 'telegram_file_limit'),
        (('message caption is too long', 'message is too long'), 'telegram_text_limit'),
    )
    for phrases, category in categories:
        if any(phrase in message for phrase in phrases):
            return category
    return 'telegram_bad_request_other'
