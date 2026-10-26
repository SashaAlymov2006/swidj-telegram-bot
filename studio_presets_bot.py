"""Chat access to the same named sound presets used by the Mini App."""
import asyncio
import hashlib
import tempfile
from urllib.parse import urlencode
from telegram import InlineKeyboardButton as Button,WebAppInfo
from ui_layout import comfortable_keyboard as Markup
from library_ui import screen
from studio_presets import load,settings

slots=asyncio.Semaphore(2)

def words(context):
    if context.user_data.get('language')=='en':
        return {'title':'My sound presets','empty':'Save your sound in the app. Your presets will appear here too.','app':'Open studio','back':'Back to studio','source':'Choose or send a track first.','working':'Applying your sound…','full':'Both processing slots are busy. Please try again shortly.'}
    return {'title':'Мои пресеты','empty':'Сохрани свой звук в приложении — пресеты появятся и здесь.','app':'Открыть студию','back':'Назад в студию','source':'Сначала выбери или пришли трек.','working':'Применяю твой звук…','full':'Обе обработки сейчас заняты. Попробуй чуть позже.'}

async def show(update,context,store,page=0):
    items=await load(store,update.effective_user.id);w=words(context);page=max(0,min(page,max(0,(len(items)-1)//5)))
    rows=[[Button(item['name'],callback_data='preset:apply:'+item['id'])] for item in items[page*5:page*5+5]]
    if page:rows.append([Button('←',callback_data=f'preset:list:{page-1}')])
    if len(items)>(page+1)*5:rows.append([Button('→',callback_data=f'preset:list:{page+1}')])
    from miniapp_server import public_url
    origin=public_url()
    if origin and update.effective_chat.type=='private':
        song=context.user_data.get('downloaded_song',{});query=urlencode({'track':song['id']}) if song.get('id') is not None else ''
        rows.append([Button(w['app'],web_app=WebAppInfo(origin+('?' +query if query else '')+'#studio'))])
    rows.append([Button(w['back'],callback_data='studio:home')])
    from html import escape
    current=context.user_data.get('downloaded_song',{}).get('title')
    caption='🎛 <b>'+escape(w['title'])+'</b>'+('' if items else '\n'+escape(w['empty']))
    if items and current:caption+='\n'+('For: ' if context.user_data.get('language')=='en' else 'Для: ')+escape(str(current)[:100])
    return await screen(update,caption,rows)

async def handle(update,context,store,retain_source):
    query=update.callback_query;await query.answer();data=query.data or ''
    if data.startswith('preset:list'):
        parts=data.split(':');return await show(update,context,store,int(parts[2]) if len(parts)==3 else 0)
    if not data.startswith('preset:apply:'):return
    uid=update.effective_user.id;item=next((item for item in await load(store,uid) if item['id']==data.rsplit(':',1)[-1]),None)
    if not item:return await show(update,context,store)
    from uploaded_media import owned_path
    source=owned_path(context.user_data.get('last_audio_path'),uid,active=True)
    w=words(context)
    if not source:return await update.effective_message.reply_text(w['source'])
    if slots.locked():return await update.effective_message.reply_text(w['full'])
    from miniapp_studio import render,probe
    from operations import stage,checkpoint
    from scratch import scratch_root
    from audio_presentation import send_music
    from track_card import card_keyboard
    await stage(w['working'])
    async with slots:
        with tempfile.TemporaryDirectory(dir=scratch_root(),prefix='preset-') as folder:
            config=dict(settings(item['settings']),format='mp3')
            target=await render(source,folder,config);checkpoint()
            digest=hashlib.sha256(str(uid).encode())
            with target.open('rb') as stream:
                for chunk in iter(lambda:stream.read(1048576),b''):digest.update(chunk)
            original=context.user_data.get('downloaded_song',{}).get('title','SwiDJ')
            title=(str(original)+' · '+item['name'])[:140]
            await retain_source(context,uid,target)
            song={'id':-(10**16+int.from_bytes(digest.digest()[:6],'big')),'title':title,'artist':'SwiDJ Studio','kind':'upload','media_kind':'audio','original_filename':title+'.mp3','duration':await probe(target),'_local_source':context.user_data['last_audio_path']}
            context.user_data['downloaded_song']=song;context.user_data['pending_effects']=[]
            message=await send_music(context.bot,uid,target,title,'SwiDJ Studio',reply_markup=card_keyboard(context,song,delivered=True))
            media=getattr(message,'audio',None)
            if media:
                song['file_id']=media.file_id
                for snapshot in context.user_data.get('track_cards',{}).values():
                    if snapshot['id']==song['id']:snapshot['file_id']=media.file_id
