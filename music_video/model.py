"""Versioned scene settings shared by preview and offline rendering."""
import math
import re

DEFAULTS = dict(version=1, preset='neon', shape='circle', spectrum='ring', particles='stars',
                particleCount=36, color='#77f2cf', color2='#8d79ff', background='#0c1020',
                backgroundKind='color', dim=.35, zoom=1.08, rotation=.1, strength=1., glow=.7,
                title='', subtitle='', start=0., end=0., fps=30, resolution=1080,
                aspect='landscape', seed=7421)
PRESETS = {
    'neon': dict(shape='circle', spectrum='ring', particles='sparks', color='#77f2cf',color2='#8d79ff',glow=.8),
    'prism': dict(shape='triangle', spectrum='ring', particles='stars',color='#ff80b5',color2='#7b8fff',rotation=.2),
    'stars': dict(shape='circle',spectrum='ring',particles='stars',color='#91bcff',color2='#d9c6ff',particleCount=80),
    'minimal':dict(shape='none',spectrum='wave',particles='none',color='#f3ece3',color2='#c6ad91',glow=.15),
    'retro':dict(shape='square',spectrum='bars',particles='none',color='#ffb36a',color2='#ff68b5',rotation=0),
    'liquid':dict(shape='circle',spectrum='wave',particles='snow',color='#6df5df',color2='#6d8fff',glow=.9),
    'stage':dict(shape='triangle',spectrum='bars',particles='sparks',color='#ffe98a',color2='#ff7498',particleCount=64),
    'photo':dict(shape='none',spectrum='bars',particles='none',color='#ffffff',color2='#cad1dc',zoom=1.15,glow=.2),
}

def validate(value):
    if not isinstance(value,dict):raise ValueError('Invalid scene')
    if set(value)-set(DEFAULTS):raise ValueError('Unknown scene setting')
    out=dict(DEFAULTS,**value)
    enums={'version':(1,), 'preset':tuple(PRESETS),'shape':('none','circle','triangle','square'),
           'spectrum':('none','ring','bars','wave'),'particles':('none','stars','sparks','snow'),
           'backgroundKind':('color','image','video'),'aspect':('landscape','portrait','square'),
           'resolution':(720,1080),'fps':(30,60)}
    for key,choices in enums.items():
        if isinstance(out[key],bool) or out[key] not in choices:raise ValueError('Invalid '+key)
    for key,low,high in [('particleCount',0,200),('seed',0,2**31-1),('dim',0,.95),('zoom',1,1.5),
                         ('rotation',-1,1),('strength',0,3),('glow',0,1),('start',0,86400),('end',0,86400)]:
        number=out[key]
        if type(number) not in (int,float) or not math.isfinite(number) or not low<=number<=high:raise ValueError('Invalid '+key)
        if key in ('particleCount','seed') and int(number)!=number:raise ValueError('Invalid '+key)
    for key in ('color','color2','background'):
        if not isinstance(out[key],str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',out[key]):raise ValueError('Invalid color')
    for key,limit in [('title',120),('subtitle',100)]:
        if not isinstance(out[key],str) or len(out[key])>limit or any(ord(c)<32 for c in out[key]):raise ValueError('Invalid text')
    if out['end'] and out['end']<=out['start']:raise ValueError('End must follow start')
    return out

def dimensions(scene):
    short=scene['resolution'];long=short*16//9
    long+=long%2
    return (long,short) if scene['aspect']=='landscape' else (short,long) if scene['aspect']=='portrait' else (short,short)
