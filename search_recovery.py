"""Owner-scoped query bookmarks, independent of expiring track snapshots."""
import secrets
import time
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def remember(context,token,query,mode='title'):
    query=str(query or '').strip()[:120]
    if not query:return
    entries=context.user_data.setdefault('search_recovery',{})
    now=time.time()
    for key in list(entries):
        if now-entries[key].get('at',0)>30*86400:entries.pop(key)
    entries[token]={'query':query,'mode':'lyrics' if mode=='lyrics' else 'title','at':now}
    while len(entries)>200:entries.pop(next(iter(entries)))

def lookup(context,token):
    entry=context.user_data.get('search_recovery',{}).get(token)
    return entry if entry and time.time()-entry.get('at',0)<=30*86400 else None

async def offer(update,context,token):
    english=context.user_data.get('language')=='en'
    entry=lookup(context,token)
    if not entry:
        message=update.effective_message
        lines=str(getattr(message,'caption',None) or getattr(message,'text',None) or '').splitlines()
        for index,line in enumerate(lines):
            if line.startswith('🎵 ') and index+1<len(lines):
                token=secrets.token_hex(5)
                remember(context,token,lines[index+1]+' '+line[2:].strip())
                entry=lookup(context,token);break
    label=('Repeat search' if english else 'Повторить поиск') if entry else ('New search' if english else 'Новый поиск')
    text=('This result has expired. You can search again.' if english else 'Этот результат устарел. Можно повторить поиск.')
    button=InlineKeyboardButton(label,callback_data='recover:'+token if entry else 'ui:search')
    return await update.effective_message.reply_text(text,reply_markup=InlineKeyboardMarkup([[button]]))
