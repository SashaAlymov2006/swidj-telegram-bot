"""Versioned scene settings shared by preview and offline rendering."""
import math
import re

DEFAULTS = dict(version=1, preset='neon', shape='circle', spectrum='ring', particles='stars',
                particleCount=36, color='#77f2cf', color2='#8d79ff', background='#0c1020',
                backgroundKind='color', dim=.35, zoom=1.08, rotation=.1, strength=1., glow=.7,
                title='', subtitle='', start=0., end=0., fps=30, resolution=1080,
                aspect='landscape', seed=7421,logoX=.5,logoY=.45,logoSize=1.,pulse=1.,
                spectrumY=.78,spectrumSize=1.,fit='cover',panX=.5,panY=.5,blur=0.,vignette=0.,
                textY=.855,textSize=1.,textColor='#ffffff',fadeIn=0.,fadeOut=0.,lyricsOn=False,lyricsY=.75,lyricsSize=1.,lyricsOffset=0.,lyricsStyle='highlight',spinLogo=False,
                lyricsBackdrop='panel',lyricsOpacity=.69,pulseMode='bass',motion='still',animationSpeed=1.,motionAmount=.5)
PRESETS = {
    'club':dict(shape='hexagon',spectrum='ripple',particles='sparks',color='#66ffd1',color2='#b782ff',pulseMode='double',motion='sway',glow=.8),
    'ocean':dict(shape='circle',spectrum='dualwave',particles='snow',color='#80eaff',color2='#709bff',background='#091a2a',pulseMode='breath',motion='float',animationSpeed=.65,glow=.35,spectrumY=.68,textY=.9),
    'constellation':dict(shape='star',spectrum='ring',particles='stars',particleCount=80,color='#e8d7ff',color2='#85c8ff',pulseMode='beat',motion='orbit',motionAmount=.25),
    'lyric':dict(shape='none',spectrum='dualwave',particles='none',background='#171020',color='#eeb6fd',color2='#a3c5ff',lyricsBackdrop='none',lyricsY=.46,lyricsSize=1.2,spectrumY=.68,textY=.9,glow=.15),
    'bloom':dict(shape='circle',spectrum='ripple',particles='snow',color='#ffb6d8',color2='#a6a2ff',background='#201329',pulseMode='breath',motion='float',motionAmount=.3,animationSpeed=.7),
    'festival':dict(shape='star',spectrum='dualwave',particles='sparks',particleCount=64,color='#ffe674',color2='#ff739e',pulseMode='beat',motion='sway',spectrumY=.68,textY=.9,glow=.7),
    'vinyl':dict(shape='circle',spectrum='mirror',particles='none',color='#e8bc80',color2='#b886db',rotation=.65,spinLogo=True,logoSize=.8),
    'tunnel':dict(shape='triangle',spectrum='ring',particles='sparks',color='#7cf9ed',color2='#ec64cf',rotation=.25,glow=.5),
    'aurora':dict(shape='circle',spectrum='wave',particles='stars',color='#82ffd4',color2='#8b78ff',particleCount=24,glow=.4),
    'grid':dict(shape='circle',spectrum='mirror',particles='none',color='#f878db',color2='#738dff',background='#110e25',spectrumY=.68),
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
    enums={'version':(1,), 'preset':tuple(PRESETS),'shape':('none','circle','triangle','square','hexagon','star'),
           'spectrum':('none','ring','bars','wave','mirror','ripple','dualwave'),'particles':('none','stars','sparks','snow'),
           'backgroundKind':('color','image','video'),'aspect':('landscape','portrait','square'),
           'resolution':(720,1080),'fps':(30,60)}
    enums['fit']=('cover','contain')
    enums['lyricsStyle']=('highlight','fade','pulse')
    enums.update(lyricsBackdrop=('panel','none'),pulseMode=('bass','beat','breath','double','off'),motion=('still','float','orbit','sway'))
    if type(out['lyricsOn']) is not bool:raise ValueError('Invalid lyrics setting')
    if type(out['spinLogo']) is not bool:raise ValueError('Invalid logo rotation')
    for key,choices in enums.items():
        if isinstance(out[key],bool) or out[key] not in choices:raise ValueError('Invalid '+key)
    for key,low,high in [('particleCount',0,200),('seed',0,2**31-1),('dim',0,.95),('zoom',1,1.5),
                         ('rotation',-1,1),('strength',0,3),('glow',0,1),('start',0,86400),('end',0,86400),
                         ('logoX',.1,.9),('logoY',.1,.9),('logoSize',.4,1.6),('pulse',0,2),
                         ('spectrumY',.2,.95),('spectrumSize',.5,1.5),('panX',0,1),('panY',0,1),
                         ('blur',0,20),('vignette',0,1),('textY',.1,.9),('textSize',.5,1.5),('fadeIn',0,3),('fadeOut',0,3),
                         ('lyricsY',.15,.9),('lyricsSize',.6,1.4),('lyricsOffset',-10,10),('lyricsOpacity',0,.9),('animationSpeed',.2,2),('motionAmount',0,1)]:
        number=out[key]
        if type(number) not in (int,float) or not math.isfinite(number) or not low<=number<=high:raise ValueError('Invalid '+key)
        if key in ('particleCount','seed') and int(number)!=number:raise ValueError('Invalid '+key)
    for key in ('color','color2','background','textColor'):
        if not isinstance(out[key],str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',out[key]):raise ValueError('Invalid color')
    for key,limit in [('title',120),('subtitle',100)]:
        if not isinstance(out[key],str) or len(out[key])>limit or any(ord(c)<32 for c in out[key]):raise ValueError('Invalid text')
    if out['end'] and out['end']<=out['start']:raise ValueError('End must follow start')
    return out

def movement(scene,t,features,w,h):
    """Visual clock is already scaled; lyric/audio clocks remain unscaled."""
    low,mid,high,rms,beat=map(float,features[:5]);u=min(w,h)
    response={'bass':low*.13+beat*.03,'beat':beat*.18,
              'breath':(.5+.5*math.sin(t*2))*.1+low*.08,
              'double':beat*(.1+.08*(.5+.5*math.sin(t*8)))+low*.04,'off':0}[scene['pulseMode']]
    cx,cy=w*scene['logoX'],h*scene['logoY'];amount=scene['motionAmount']
    angle=t*scene['rotation']*.7
    if scene['motion']=='float':cx+=math.sin(t*.7)*u*.025*amount;cy+=math.sin(t*.9)*u*.04*amount
    if scene['motion']=='orbit':cx+=math.sin(t*.65)*u*.07*amount;cy+=math.cos(t*.65)*u*.04*amount
    if scene['motion']=='sway':angle+=math.sin(t*1.4)*.3*amount
    radius=u*.19*scene['logoSize']*(1+response*scene['strength']*scene['pulse'])
    return cx,cy,radius,angle

def dimensions(scene):
    short=scene['resolution'];long=short*16//9
    long+=long%2
    return (long,short) if scene['aspect']=='landscape' else (short,long) if scene['aspect']=='portrait' else (short,short)
