"""Short bilingual onboarding; feature details are opened only on request."""
from telegram import InlineKeyboardButton as Button, InlineKeyboardMarkup as Markup, WebAppInfo
from html import escape

from guide_inventory import WELCOME,TOPICS

def lang(context):return 'en' if context.user_data.get('language')=='en' else 'ru'

def panel(context,topic='home',*,app_url=None):
    en=lang(context)=='en';buttons=[]
    if topic in TOPICS:
        row=TOPICS[topic];text='<b>'+escape(row[1 if en else 0])+'</b>\n\n'+escape(row[3 if en else 2])
        actions={'search':('🔎 Find a song' if en else '🔎 Найти песню','ui:search'),
                 'library':('⭐ Your music' if en else '⭐ Моя музыка','ui:favorites'),
                 'studio':('🎛 Studio in chat' if en else '🎛 Студия в чате','ui:audio')}
        if topic in actions:
            title,target=actions[topic];buttons.append([Button(title,callback_data=target)])
        buttons.append([Button('← All features' if en else '← Все возможности',callback_data='features:home')])
    else:
        text='<b>📚 All SwiDJ features</b>' if en else '<b>📚 Все возможности SwiDJ</b>'
        keys=list(TOPICS)
        for i in range(0,len(keys),2):buttons.append([Button(TOPICS[k][1 if en else 0],callback_data='features:'+k) for k in keys[i:i+2]])
    if app_url:buttons.append([Button('✨ Open Mini App' if en else '✨ Открыть Mini App',web_app=WebAppInfo(app_url),style='primary')])
    buttons.append([Button('← Menu' if en else '← Меню',callback_data='ui:home')])
    return text,Markup(buttons)

async def callback(update,context):
    query=update.callback_query;await query.answer()
    from miniapp_server import public_url
    from artist_ui import edit_catalog
    app_url=public_url() if update.effective_chat.type=='private' else None
    text,keyboard=panel(context,query.data.split(':',1)[-1],app_url=app_url)
    return await edit_catalog(query.message,text,parse_mode='HTML',reply_markup=keyboard,disable_web_page_preview=True)
