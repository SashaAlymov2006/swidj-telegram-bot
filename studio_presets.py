"""Owner-scoped named sound settings shared by the bot and Mini App."""
import asyncio
import re
import math
import secrets
from app_dsp import parameters
from miniapp_studio import EFFECTS,number

MAX_PRESETS=20

def settings(value):
    if not isinstance(value,dict):raise ValueError('Invalid preset')
    linked=value.get('linked',False)
    effects=value.get('effects',[])
    if type(linked) is not bool or not isinstance(effects,list) or len(effects)>8 or any(not isinstance(effect,str) or effect not in EFFECTS for effect in effects):
        raise ValueError('Invalid preset')
    speed=number(value,'speed',1,.5,2);pitch=number(value,'pitch',0,-12,12)
    return {'speed':speed,'pitch':12*math.log2(speed) if linked else pitch,
            'bass':number(value,'bass',0,-6,9),'treble':number(value,'treble',0,-6,6),
            'ambience':number(value,'ambience',100,0,100),'fade':number(value,'fade',0,0,10),
            'linked':linked,'effects':list(dict.fromkeys(effects)),'params':parameters(value)}

async def load(store,uid):
    return (await asyncio.to_thread(store.load_named,'studio_presets')).get(uid,[])

async def change(store,uid,payload):
    if not isinstance(payload,dict):raise ValueError('Invalid preset')
    items=list(await load(store,uid));action=payload.get('action');identifier=str(payload.get('id',''))
    if action=='remove':
        if not any(item['id']==identifier for item in items):raise KeyError(identifier)
        items=[item for item in items if item['id']!=identifier]
    elif action=='save':
        name=re.sub(r'[\x00-\x1f\x7f]',' ',str(payload.get('name','')))
        name=' '.join(name.split())[:40]
        if not name:raise ValueError('Missing name')
        config=settings(payload.get('settings'))
        if identifier:
            if not any(item['id']==identifier for item in items):raise KeyError(identifier)
            items=[dict(item,name=name,settings=config) if item['id']==identifier else item for item in items]
        else:
            if len(items)>=MAX_PRESETS:raise OverflowError('Preset limit')
            items.append({'id':secrets.token_hex(4),'name':name,'settings':config})
    else:raise ValueError('Invalid preset action')
    await asyncio.to_thread(store.save_named,'studio_presets',uid,items)
    return items

def register(app,bridge):
    from aiohttp import web
    async def endpoint(request):
        uid=request['user']['id'];bridge.allowed(uid,'studio')
        if request.method=='GET':return web.json_response({'presets':await load(bridge.store,uid)})
        try:items=await change(bridge.store,uid,await request.json())
        except KeyError:raise web.HTTPNotFound() from None
        except OverflowError:raise web.HTTPConflict() from None
        except (ValueError,TypeError):raise web.HTTPBadRequest() from None
        return web.json_response({'presets':items})
    app.router.add_get('/api/presets',endpoint);app.router.add_post('/api/presets',endpoint)
