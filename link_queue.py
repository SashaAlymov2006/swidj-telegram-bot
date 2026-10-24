"""Small sequential link batches; catalog links pause for an explicit version choice."""
import asyncio
import os
import secrets
from html import escape
from telegram import InlineKeyboardButton as Button
from ui_layout import comfortable_keyboard as Markup
from operations import checkpoint, stage, _current, cancel

MAX_LINKS=5

def current(context, token, index=None):
    queue=context.user_data.get("link_queues",{}).get(token)
    return queue if queue and not queue.get("stopped") and (index is None or queue["index"]==index) else None

def skip_button(token,index):
    return Button("Пропустить трек",callback_data=f"batch:skip:{token}:{index}")

async def create(update,context,items):
    token=secrets.token_hex(5)
    queues=context.user_data.setdefault("link_queues",{})
    queues[token]={"items":items[:MAX_LINKS],"index":0,"done":0,"failed":0,"stopped":False}
    while len(queues)>4:
        queues.pop(next(iter(queues)))
    text=f"🎵 <b>Очередь · {len(items[:MAX_LINKS])} треков</b>\nАудио по порядку. Для каталожных ссылок — выбор версии."
    if len(items)>MAX_LINKS:
        text+="\nЗа один раз — первые 5 ссылок."
    await update.effective_message.reply_text(text,parse_mode="HTML",reply_markup=Markup([
        [Button("⬇ Скачать по очереди",callback_data="batch:run:"+token,style="primary")],
        [Button("Отмена",callback_data="batch:stop:"+token)]]))

async def run(update,context,token,bot_module):
    queue=current(context,token)
    if not queue:
        return await update.effective_message.reply_text("Очередь уже завершена или отменена.")
    op=_current.get()
    if op:
        queue["op_token"]=op.token
    while queue["index"]<len(queue["items"]):
        checkpoint()
        if queue.get("stopped"): return
        index=queue["index"];item=queue["items"][index]
        await stage(f"Очередь · {index+1}/{len(queue['items'])}")
        if item["platform"] in ("yandex","vk","apple","spotify"):
            from catalog_links import catalog_metadata
            from versions import request_versions
            try:
                metadata=await asyncio.to_thread(bot_module.spotify_to_metadata,item["url"]) if item["platform"]=="spotify" else await asyncio.to_thread(catalog_metadata,item["platform"],item["url"])
                checkpoint()
                from hashlib import sha256
                song=dict(metadata,id=-(10**15+int.from_bytes(sha256(item["url"].encode()).digest()[:6],"big")),url=item["url"],source=item["platform"])
            except Exception:
                checkpoint()
                context.user_data["awaiting_catalog"]={"url":item["url"],"platform":item["platform"],"queue_ref":[token,index]}
                return await update.effective_message.reply_text(
                    f"Трек {index+1}/{len(queue['items'])}: не удалось прочитать название. Напиши название и исполнителя — продолжим с этой песней.",
                    reply_markup=Markup([[skip_button(token,index)],[Button("Отменить очередь",callback_data="batch:stop:"+token)]]))
            return await request_versions(update,context,song,mode="queue",queue_ref=[token,index])
        path=None
        sent=False
        try:
            if item["platform"] in ("tiktok","instagram"):
                path=await asyncio.to_thread(bot_module.download_youtube_video,item["url"],1080)
                from video_presentation import probe_video
                metadata=await asyncio.to_thread(probe_video,path)
                checkpoint()
                with open(path,"rb") as media:
                    await context.bot.send_video(chat_id=update.effective_chat.id,video=media,supports_streaming=True,**metadata)
                queue["done"]+=1
                queue["index"]+=1
                continue
            from audio_presentation import send_music
            from track_card import card_keyboard
            if item["platform"]=="youtube":
                path,info=await asyncio.to_thread(bot_module.download_youtube_audio,item["url"])
                title,artist=bot_module.extract_youtube_metadata(info);cover=info.get("thumbnail")
            else:
                data=await asyncio.to_thread(bot_module.download_soundcloud_audio,item["url"])
                path,title,artist,cover=data["path"],data.get("title"),data.get("artist"),data.get("cover")
            from hashlib import sha256
            song={"id":-(10**15+int.from_bytes(sha256(item["url"].encode()).digest()[:6],"big")),"title":title or "Аудио","artist":artist or "","url":item["url"],"cover":cover}
            checkpoint()
            await send_music(context.bot,update.effective_chat.id,path,title,artist,cover,reply_markup=card_keyboard(context,song,delivered=True))
            sent=True
            await bot_module.retain_audio_source(context,update.effective_user.id,path)
            context.user_data["downloaded_song"]=song
            context.user_data["pending_effects"]=[]
            queue["done"]+=1
        except Exception:
            if sent:
                queue["done"]+=1
                queue["index"]+=1
                await update.effective_message.reply_text("Трек отправлен; рабочую копию для студии сохранить не удалось.")
                continue
            queue["failed"]+=1
            # Keep the exact source available through the existing link retry menu.
            request_token=secrets.token_hex(6)
            requests=context.user_data.setdefault("dl_requests",{})
            requests[request_token]=dict(item)
            while len(requests)>20: requests.pop(next(iter(requests)))
            await update.effective_message.reply_text(
                f"Трек {index+1}: не удалось скачать. Продолжаю очередь.",
                reply_markup=Markup([[Button("🔄 Повторить этот трек",callback_data=("dl_video|1080|" if item["platform"] in ("tiktok","instagram") else "dl_audio|")+request_token)]]))
        finally:
            if path and os.path.isfile(path):
                from scratch import remove_owned_file
                remove_owned_file(path)
                if os.path.isfile(path): os.remove(path)
        queue["index"]+=1
    queue["stopped"]=True
    await update.effective_message.reply_text(
        f"✓ Очередь завершена · отправлено {queue['done']} из {len(queue['items'])}" +
        (f" · пропущено {queue['failed']}" if queue["failed"] else ""))

async def advance(update,context,reference,bot_module,*,skipped=False):
    token,index=reference
    queue=current(context,token,index)
    if not queue: return
    queue["failed" if skipped else "done"]+=1
    queue["index"]+=1
    if context.user_data.get("awaiting_catalog",{}).get("queue_ref") == list(reference):
        context.user_data.pop("awaiting_catalog",None)
    return await run(update,context,token,bot_module)

async def stop(update,context):
    token=update.callback_query.data.rsplit(":",1)[-1]
    queue=context.user_data.get("link_queues",{}).get(token)
    if queue and not queue.get("stopped"):
        queue["stopped"]=True
        cancel(update.effective_user.id,queue.get("op_token",""))
        if context.user_data.get("awaiting_catalog",{}).get("queue_ref",[""])[0] == token:
            context.user_data.pop("awaiting_catalog",None)
        await update.callback_query.answer("Очередь отменена.")
        await update.effective_message.reply_text("Очередь отменена.")
    else:
        await update.callback_query.answer("Очередь уже завершена.")
