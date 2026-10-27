"""Compact chat track details and paged artist discovery across public catalogs."""
import asyncio
import re
import secrets
from telegram import InlineKeyboardButton as Button
from ui_layout import comfortable_keyboard as Markup
from artist_catalog import browse,creator,details,PROVIDERS,NAMES

def tr(context,ru,en):return en if context.user_data.get('language')=='en' else ru

async def info(update,context,song):
    token=secrets.token_hex(5);views=context.user_data.setdefault('artist_views',{});views[token]=dict(song)
    while len(views)>8:views.pop(next(iter(views)))
    data=details(song);lines=[data.get('title',''),data.get('artist','')]
    if data.get('duration'):lines.append(f"{data['duration']//60}:{data['duration']%60:02d}")
    for field,ru,en in [('album','Альбом','Album'),('release_date','Релиз','Release'),('upload_date','Опубликовано','Published'),('source','Источник','Source')]:
        if data.get(field):lines.append(tr(context,ru,en)+': '+data[field])
    rows=[]
    if creator(song):rows.append([Button(tr(context,'Треки автора','Artist tracks'),callback_data=f'art:{token}:all:0')])
    if data.get('url'):rows.append([Button(tr(context,'Открыть источник','Open source'),url=data['url'])])
    return await update.effective_message.reply_text('\n'.join(lines),reply_markup=Markup(rows),parse_mode=None,disable_web_page_preview=True)

async def callback(update,context):
    query=update.callback_query;await query.answer()
    selected=re.fullmatch(r'arp:([0-9a-f]{10}):(\d{1,2})',query.data or '')
    if selected:
        rows=context.user_data.get('artist_pages',{}).get(selected[1],[])
        if int(selected[2])>=len(rows):return
        from track_card import show_card
        origin=context.user_data.get('artist_page_origins',{}).get(selected[1])
        back=[[Button(tr(context,'← К автору','← Artist'),callback_data=origin)]] if origin else None
        return await show_card(update,context,rows[int(selected[2])],extra_rows=back)
    match=re.fullmatch(r'art:([0-9a-f]{10}):(all|yt|sc|aud|jam):(\d{1,3})',query.data or '')
    if not match:return
    song=context.user_data.get('artist_views',{}).get(match[1])
    if not song:return await query.message.reply_text(tr(context,'Открой карточку трека ещё раз.','Open the track card again.'))
    page=await asyncio.to_thread(browse,song,match[2],int(match[3]));token=secrets.token_hex(5)
    store=context.user_data.setdefault('artist_pages',{});store[token]=page['tracks']
    origins=context.user_data.setdefault('artist_page_origins',{});origins[token]=query.data
    while len(store)>8:
        old=next(iter(store));store.pop(old);origins.pop(old,None)
    buttons=[[Button(item['title'][:70],callback_data=f'arp:{token}:{index}')] for index,item in enumerate(page['tracks'])]
    navigation=[]
    if page['offset']:navigation.append(Button('←',callback_data=f"art:{match[1]}:{match[2]}:{page['offset']-10}"))
    if page['next_offset'] is not None:navigation.append(Button(tr(context,'Ещё →','More →'),callback_data=f"art:{match[1]}:{match[2]}:{page['next_offset']}"))
    if navigation:buttons.append(navigation)
    # A single compact row, not one large section per provider.
    buttons.append([Button(tr(context,'Все','All'),callback_data=f'art:{match[1]}:all:0')]+[Button(NAMES[p],callback_data=f'art:{match[1]}:{p}:0') for p in page['available_sources'] if p!=match[2]])
    content=page['name']+'\n'+tr(context,'Треки автора','Artist tracks')
    if not page['tracks']:content+='\n'+tr(context,'Записи не найдены.','No recordings found.')
    return await query.message.edit_text(content,reply_markup=Markup(buttons),parse_mode=None)
