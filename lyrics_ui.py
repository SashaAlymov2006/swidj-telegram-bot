"""Read lyrics inside chat, with bounded per-user snapshots and one paged message."""
import re
import secrets
from telegram import InlineKeyboardButton as Button
from ui_layout import comfortable_keyboard as Markup
from app_lyrics import shared
from aiohttp import web


def text(context,ru,en):return en if context.user_data.get('language')=='en' else ru


def pages(value):
    result=[]
    while value:
        split=value.rfind('\n',0,3400) if len(value)>3400 else len(value)
        if split<1:split=min(3400,len(value))
        result.append(value[:split]);value=value[split:].lstrip('\n')
    return result or ['']


async def render(update,context,token,index=0,page=0,edit=True):
    matches=context.user_data.get('lyrics_views',{}).get(token)
    if not matches or not 0<=index<len(matches):
        return await update.effective_message.reply_text(text(context,'Открой текст песни ещё раз.','Open the lyrics again.'))
    item=matches[index];parts=pages(item['text']);page=max(0,min(page,len(parts)-1))
    body=item['title']+' — '+item['artist']+'\n\n'+parts[page]
    rows=[];navigation=[]
    if page:navigation.append(Button('←',callback_data=f'lyr:{token}:{index}:{page-1}'))
    if len(parts)>1:navigation.append(Button(f'{page+1}/{len(parts)}',callback_data=f'lyr:{token}:{index}:{page}'))
    if page+1<len(parts):navigation.append(Button('→',callback_data=f'lyr:{token}:{index}:{page+1}'))
    if navigation:rows.append(navigation)
    if len(matches)>1:rows.append([Button(text(context,'Другой текст','Another version'),callback_data=f'lyr:{token}:{(index+1)%len(matches)}:0')])
    if item.get('source_url'):rows.append([Button(text(context,'Открыть источник','Open source'),url=item['source_url'])])
    options={'text':body,'reply_markup':Markup(rows),'parse_mode':None,'disable_web_page_preview':True}
    if edit:
        from telegram.error import BadRequest
        try:return await update.callback_query.message.edit_text(**options)
        except BadRequest as error:
            if 'not modified' in str(error).lower():return
            raise
    return await update.effective_message.reply_text(**options)


async def show(update,context,song):
    origin=song.get('_catalog_song') or song
    try:result=await shared.lookup(str(origin.get('title','')),str(origin.get('artist','')),origin.get('duration'))
    except web.HTTPException:
        return await update.effective_message.reply_text(text(context,'Попробуй открыть текст чуть позже.','Try opening the lyrics again shortly.'))
    matches=result.get('matches') or []
    if not matches:
        return await update.effective_message.reply_text(text(context,'Текст для этой записи не найден.','No lyrics found for this recording.'))
    views=context.user_data.setdefault('lyrics_views',{});token=secrets.token_hex(5);views[token]=matches
    while len(views)>8:views.pop(next(iter(views)))
    return await render(update,context,token,edit=False)


async def callback(update,context):
    await update.callback_query.answer()
    match=re.fullmatch(r'lyr:([0-9a-f]{10}):(\d):(\d{1,2})',update.callback_query.data or '')
    if match:return await render(update,context,match[1],int(match[2]),int(match[3]))
