"""Compact chat track details and paged artist discovery across public catalogs."""
import asyncio
import re
import secrets
from telegram import InlineKeyboardButton as Button
from ui_layout import comfortable_keyboard as Markup
from artist_catalog import browse,creator,details,PROVIDERS,NAMES

def tr(context,ru,en):return en if context.user_data.get('language')=='en' else ru


def discovery_button(context,query,token=None):
    token=token or secrets.token_hex(5);queries=context.user_data.setdefault('artist_discovery_queries',{})
    queries[token]=str(query)[:120]
    while len(queries)>8:queries.pop(next(iter(queries)))
    return Button(tr(context,'👤 Исполнители','👤 Artists'),callback_data='afd:'+token)

async def info(update,context,song):
    token=secrets.token_hex(5);views=context.user_data.setdefault('artist_views',{});views[token]=dict(song)
    while len(views)>8:views.pop(next(iter(views)))
    data=details(song);lines=[data.get('title',''),data.get('artist','')]
    if data.get('duration'):lines.append(f"{data['duration']//60}:{data['duration']%60:02d}")
    for field,ru,en in [('album','Альбом','Album'),('release_date','Релиз','Release'),('upload_date','Опубликовано','Published'),('source','Источник','Source')]:
        if data.get(field):lines.append(tr(context,ru,en)+': '+data[field])
    rows=[]
    if creator(song):
        rows.append([Button(tr(context,'Треки автора','Artist tracks'),callback_data=f'art:{token}:all:0')])
        rows.append([Button(tr(context,'Альбомы и релизы','Albums & releases'),callback_data=f'arl:{token}:0')])
    if data.get('url'):rows.append([Button(tr(context,'Открыть источник','Open source'),url=data['url'])])
    return await update.effective_message.reply_text('\n'.join(lines),reply_markup=Markup(rows),parse_mode=None,disable_web_page_preview=True)

async def callback(update,context):
    query=update.callback_query;await query.answer()
    discovery=re.fullmatch(r'afd:([0-9a-f]{10})',query.data or '')
    if discovery:
        from expanded_catalog import discover
        name=context.user_data.get('artist_discovery_queries',{}).get(discovery[1])
        if not name:return
        rows=await asyncio.to_thread(discover,name);buttons=[];views=context.user_data.setdefault('artist_views',{})
        for row in rows:
            token=secrets.token_hex(5);views[token]=row
            label=row['name']+' · '+(row.get('description') or row['source'])
            buttons.append([Button(label[:70],callback_data='art:'+token+':all:0')])
        while len(views)>24:views.pop(next(iter(views)))
        text=tr(context,'Исполнители','Artists')+' · '+name
        if not buttons:text+='\n'+tr(context,'Профили не найдены. Поиск треков остаётся доступен.','No profiles found. Track search remains available.')
        return await query.message.edit_text(text,reply_markup=Markup(buttons) if buttons else None,parse_mode=None)
    profile=re.fullmatch(r'arf:([0-9a-f]{10}):(\d{1,16})',query.data or '')
    if profile:
        views=context.user_data.get('artist_views',{})
        if profile[1] not in views:return
        views[profile[1]]=dict(views[profile[1]],_release_artist_id=profile[2])
        match=re.fullmatch(r'(arl|alb):([0-9a-f]{10}):(?:([A-Za-z0-9-]{1,40}):)?(\d{1,3})',f'arl:{profile[1]}:0')
        return await release_page(update,context,match)
    selected=re.fullmatch(r'arp:([0-9a-f]{10}):(\d{1,2})',query.data or '')
    if selected:
        rows=context.user_data.get('artist_pages',{}).get(selected[1],[])
        if int(selected[2])>=len(rows):return
        from track_card import show_card
        origin=context.user_data.get('artist_page_origins',{}).get(selected[1])
        back=[[Button(tr(context,'← К автору','← Artist'),callback_data=origin)]] if origin else None
        return await show_card(update,context,rows[int(selected[2])],extra_rows=back)
    release_match=re.fullmatch(r'(arl|alb):([0-9a-f]{10}):(?:([A-Za-z0-9-]{1,40}):)?(\d{1,3})',query.data or '')
    if release_match:
        return await release_page(update,context,release_match)
    remix=re.fullmatch(r'arm:([0-9a-f]{10}):(\d{1,3})',query.data or '')
    if remix:
        song=context.user_data.get('artist_views',{}).get(remix[1])
        if not song:return await query.message.reply_text(tr(context,'Открой карточку трека ещё раз.','Open the track card again.'))
        page=await asyncio.to_thread(browse,song,'all',int(remix[2]),remixes=True)
        return await track_page(update,context,page,remix[1],remix=True)
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
    buttons.append([Button(tr(context,'Альбомы','Albums'),callback_data=f'arl:{match[1]}:0'),Button(tr(context,'Ремиксы','Remixes'),callback_data=f'arm:{match[1]}:0')])
    # A single compact row, not one large section per provider.
    buttons.append([Button(tr(context,'Все','All'),callback_data=f'art:{match[1]}:all:0')]+[Button(NAMES[p],callback_data=f'art:{match[1]}:{p}:0') for p in page['available_sources'] if p!=match[2]])
    content=page['name']+'\n'+tr(context,'Треки автора','Artist tracks')
    if not page['tracks']:content+='\n'+tr(context,'Записи не найдены.','No recordings found.')
    return await query.message.edit_text(content,reply_markup=Markup(buttons),parse_mode=None)


async def track_page(update,context,page,origin,*,remix=False,album_id=None):
    """Catalog songs use the same cards and up-to-five-version download flow."""
    token=secrets.token_hex(5);store=context.user_data.setdefault('artist_pages',{})
    store[token]=page['tracks'];origins=context.user_data.setdefault('artist_page_origins',{})
    prefix=f'alb:{origin}:{album_id}' if album_id else f'arm:{origin}'
    origins[token]=f"{prefix}:{page['offset']}"
    while len(store)>8:
        old=next(iter(store));store.pop(old);origins.pop(old,None)
    buttons=[]
    for index,item in enumerate(page['tracks']):
        label=(str(item['track_number'])+'. ' if album_id else '')+item['title']
        buttons.append([Button(label[:70],callback_data=f'arp:{token}:{index}')])
    nav=[]
    if page['offset']:nav.append(Button('←',callback_data=f"{prefix}:{page['offset']-10}"))
    if page['next_offset'] is not None:nav.append(Button(tr(context,'Ещё →','More →'),callback_data=f"{prefix}:{page['next_offset']}"))
    if nav:buttons.append(nav)
    if page.get('source_url'):buttons.append([Button(page.get('source','Apple Music')+' ↗',url=page['source_url'])])
    buttons.append([Button(tr(context,'← Альбомы','← Albums') if album_id else tr(context,'← Треки автора','← Artist tracks'),callback_data=f'arl:{origin}:0' if album_id else f'art:{origin}:all:0')])
    content=page['name']+'\n'+(page.get('title') or tr(context,'Ремиксы','Remixes'))
    if not page['tracks']:content+='\n'+tr(context,'Записи не найдены.','No recordings found.')
    return await update.callback_query.message.edit_text(content,reply_markup=Markup(buttons),parse_mode=None,disable_web_page_preview=True)


async def release_page(update,context,match):
    from release_catalog import releases,album
    query=update.callback_query;kind,origin,identifier,raw_offset=match.groups()
    song=context.user_data.get('artist_views',{}).get(origin)
    if not song:return await query.message.reply_text(tr(context,'Открой карточку трека ещё раз.','Open the track card again.'))
    offset=int(raw_offset)
    if offset%10 or offset>990:return
    try:
        if kind=='alb' and identifier:
            result=await asyncio.to_thread(album,song,identifier);tracks=result['tracks']
            page=dict(name=result['name'],title=result['album']['title'],source_url=result['album']['source_url'],source=result['source'],
                      tracks=tracks[offset:offset+10],offset=offset,next_offset=offset+10 if offset+10<len(tracks) else None)
            return await track_page(update,context,page,origin,album_id=identifier)
        if kind!='arl' or identifier:return
        result=await asyncio.to_thread(releases,song,offset)
    except Exception:
        return await query.message.reply_text(tr(context,'Не удалось открыть каталог. Попробуй ещё раз чуть позже.','Could not open the catalog. Please try again shortly.'))
    labels={'album':tr(context,'Альбом','Album'),'single':tr(context,'Сингл','Single'),'ep':'EP'}
    buttons=[[Button((item['title']+' · '+labels[item['kind']])[:70],callback_data=f"alb:{origin}:{item['id']}:0")] for item in result['releases']]
    if result.get('profiles') and not result.get('selected_profile'):
        buttons=[[Button((p['name']+' · '+p['example'])[:70],callback_data=f"arf:{origin}:{p['id']}")] for p in result['profiles']]
    nav=[]
    if offset:nav.append(Button('←',callback_data=f'arl:{origin}:{offset-10}'))
    if result['next_offset'] is not None:nav.append(Button(tr(context,'Ещё →','More →'),callback_data=f"arl:{origin}:{result['next_offset']}"))
    if nav:buttons.append(nav)
    buttons.append([Button(tr(context,'← Треки автора','← Artist tracks'),callback_data=f'art:{origin}:all:0')])
    content=result['name']+'\n'+tr(context,'Альбомы и релизы','Albums & releases')
    if result.get('profiles') and not result.get('selected_profile'):content+='\n'+tr(context,'Выбери исполнителя по его релизу:','Choose the artist by their release:')
    elif not result['releases']:content+='\n'+tr(context,'Альбомы здесь не найдены. Треки автора доступны отдельно.','No albums found here. Artist tracks remain available separately.')
    return await query.message.edit_text(content,reply_markup=Markup(buttons),parse_mode=None)
