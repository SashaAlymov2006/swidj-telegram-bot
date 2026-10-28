"""CPU-only deterministic scene renderer. Run in its own process, never in bot polling."""
import argparse
import bisect
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import numpy as np
from PIL import Image,ImageDraw,ImageFilter,ImageFont,ImageOps
from .model import validate,dimensions

RATE=15360
HOP=512
FFT=1024
BANDS=48

def ffmpeg():
    executable=os.getenv('MUSIC_VIDEO_FFMPEG') or shutil.which('ffmpeg')
    if not executable:
        import imageio_ffmpeg
        executable=imageio_ffmpeg.get_ffmpeg_exe()
    return executable

def run(args):
    subprocess.run([ffmpeg(),'-nostdin','-hide_banner','-v','error',*args],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)

def progress(folder,stage,value):
    target=Path(folder)/'progress.json';pending=target.with_suffix('.pending')
    pending.write_text(json.dumps({'stage':stage,'progress':round(min(1,max(0,value)),4)}),encoding='utf-8')
    os.replace(pending,target)

def analyse(folder):
    folder=Path(folder);progress(folder,'analysis',0)
    run(['-y','-protocol_whitelist','file,pipe','-i',str(folder/'audio.input'),'-vn','-ac','1','-ar',str(RATE),'-f','f32le',str(folder/'audio.f32')])
    pcm=np.memmap(folder/'audio.f32',dtype='<f4',mode='r')
    if not len(pcm):raise ValueError('No audio')
    duration=len(pcm)/RATE;count=math.ceil(len(pcm)/HOP)
    if not (folder/'lyric_source.json').is_file():
        # Read bounded embedded tags, never infer a song identity from a filename.
        tag_process=subprocess.Popen([ffmpeg(),'-nostdin','-v','error','-protocol_whitelist','file,pipe','-i',str(folder/'audio.input'),'-f','ffmetadata','pipe:1'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        try:
            raw=tag_process.stdout.read(16385)
            if len(raw)<=16384:
                tags={line.partition('=')[0].casefold():line.partition('=')[2] for line in raw.decode('utf-8',errors='replace').splitlines() if '=' in line}
                from .lyrics import source_metadata
                source=source_metadata({'title':tags.get('title'),'artist':tags.get('artist'),'duration':duration})
                if source:(folder/'lyric_source.json').write_text(json.dumps(source),encoding='utf-8')
        finally:
            if tag_process.poll() is None:tag_process.kill()
            tag_process.wait();tag_process.stdout.close()
    features=np.lib.format.open_memmap(folder/'features.npy',mode='w+',dtype=np.float32,shape=(count,5+BANDS))
    frequencies=np.fft.rfftfreq(FFT,1/RATE);edges=np.geomspace(30,7000,BANDS+1)
    indices=[np.flatnonzero((frequencies>=a)&(frequencies<b)) for a,b in zip(edges[:-1],edges[1:])]
    windows=np.hanning(FFT);previous=np.zeros(5+BANDS,dtype=np.float32);last_low=0.
    for index in range(count):
        segment=np.zeros(FFT);samples=pcm[index*HOP:index*HOP+FFT];segment[:len(samples)]=samples
        spectrum=np.abs(np.fft.rfft(segment*windows))/(FFT/2)
        values=np.array([np.mean(spectrum[(frequencies>=a)&(frequencies<b)]) for a,b in [(30,180),(180,2500),(2500,7000)]])
        rms=float(np.sqrt(np.mean(segment**2)))
        bars=np.array([float(np.max(spectrum[ix])) if len(ix) else float(np.interp((edges[n]+edges[n+1])/2,frequencies,spectrum)) for n,ix in enumerate(indices)])
        energy=np.clip((20*np.log10(np.maximum(np.r_[values,rms,bars],1e-6))+65)/55,0,1)
        beat=min(1,max(0,float(energy[0])-last_low)*5);last_low=float(energy[0])
        current=np.r_[energy[:4],beat,energy[4:]]
        speed=np.where(current>previous,.65,.15);previous=previous+(current-previous)*speed
        features[index]=previous
        if index%300==0:progress(folder,'analysis',index/count*.8)
    features.flush();del features;del samples;pcm._mmap.close();del pcm
    (folder/'audio.f32').unlink(missing_ok=True)
    run(['-y','-protocol_whitelist','file,pipe','-i',str(folder/'audio.input'),'-vn','-c:a','libmp3lame','-b:a','160k',str(folder/'preview.mp3')])
    analyse_assets(folder)
    (folder/'analysis.json').write_text(json.dumps({'duration':duration,'featureRate':30,'frames':count,'backgroundKind':background_type(folder)}),encoding='utf-8')
    progress(folder,'ready',1)

def background_type(folder):
    return 'video' if (folder/'background-preview.mp4').exists() else 'image' if (folder/'background.png').exists() else 'color'

def analyse_assets(folder):
    folder=Path(folder)
    changes=folder/'assets_changed.json'
    names=json.loads(changes.read_text()) if changes.is_file() else ['background','logo']
    if not isinstance(names,list) or any(name not in ('background','logo') for name in names):raise ValueError('Invalid assets')
    for name in names:
        for suffix in ('.png','-poster.png','-preview.mp4'):(folder/(name+suffix)).unlink(missing_ok=True)
        source=folder/(name+'.input')
        if not source.exists():continue
        try:
            with Image.open(source) as image:
                if image.width*image.height>32_000_000:raise ValueError('Image too large')
                normalized=ImageOps.exif_transpose(image).convert('RGBA');normalized.thumbnail((2400,2400));normalized.save(folder/(name+'.png'))
        except (Image.UnidentifiedImageError,OSError):
            if name=='logo':raise ValueError('Logo must be an image') from None
            run(['-y','-protocol_whitelist','file,pipe','-i',str(source),'-an','-frames:v','1','-vf','scale=960:960:force_original_aspect_ratio=decrease:force_divisible_by=2',str(folder/'background-poster.png')])
            run(['-y','-protocol_whitelist','file,pipe','-i',str(source),'-an','-vf','scale=640:640:force_original_aspect_ratio=decrease:force_divisible_by=2','-c:v','libx264','-preset','ultrafast','-crf','30','-pix_fmt','yuv420p','-threads','1','-movflags','+faststart',str(folder/'background-preview.mp4')])
    if (folder/'analysis.json').is_file():
        metadata=json.loads((folder/'analysis.json').read_text());metadata['backgroundKind']=background_type(folder)
        (folder/'analysis.json').write_text(json.dumps(metadata),encoding='utf-8')
    progress(folder,'ready',1)

def sample(features,t):
    index=max(0,min(len(features)-1,t*30));left=int(index);right=min(len(features)-1,left+1)
    return features[left]*(1-(index-left))+features[right]*(index-left)

def rgb(value):return tuple(int(value[i:i+2],16) for i in (1,3,5))
def mix(a,b,t):return tuple(round(x*(1-t)+y*t) for x,y in zip(a,b))
def fraction(value):return value-math.floor(value)
def rand(index,seed):return fraction(math.sin(index*127.1+seed*311.7)*43758.5453)

def font(size):
    paths=[os.getenv('MUSIC_VIDEO_FONT',''),'C:/Windows/Fonts/segoeui.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']
    for path in paths:
        if path and Path(path).is_file():return ImageFont.truetype(path,max(10,int(size)))
    return ImageFont.load_default(size=max(10,int(size)))

class Scene:
    def __init__(self,folder,config):
        self.folder=Path(folder);self.config=config;self.w,self.h=dimensions(config);self.unit=min(self.w,self.h)
        self.logo=Image.open(self.folder/'logo.png').convert('RGBA') if (self.folder/'logo.png').exists() else None
        self.background=Image.open(self.folder/'background.png').convert('RGB') if (self.folder/'background.png').exists() else None
        self.titlefont=font(self.unit*.042);self.subfont=font(self.unit*.025)
        metadata=json.loads((self.folder/'analysis.json').read_text())
        self.duration=min(config['end'] or metadata['duration'],metadata['duration'])-config['start']
        self.lyrics=[]
        if config['lyricsOn'] and (self.folder/'lyrics.json').is_file():self.lyrics=json.loads((self.folder/'lyrics.json').read_text(encoding='utf-8'))['lines']
        self.lyric_times=[line['at'] for line in self.lyrics]
        self.vignette=Image.radial_gradient('L').resize((self.w,self.h)).point(lambda v:round(v*config['vignette']*.85))
        self.gradient=Image.new('RGB',(self.w,self.h));row=ImageDraw.Draw(self.gradient)
        for y in range(self.h):row.line((0,y,self.w,y),fill=mix(rgb(config['background']),tuple(int(v*.18) for v in rgb(config['color2'])),y/self.h))

    def frame(self,t,features,video=None):
        s=self.config;w,h,u=self.w,self.h,self.unit;low,mid,high,rms,beat=features[:5];strength=s['strength']
        zoom=1 if s['fit']=='contain' else 1+(s['zoom']-1)*(.5+.5*math.sin(t*.2))
        source=video if video is not None else self.background if s['backgroundKind']=='image' else None
        image=self.gradient.copy()
        if source is not None:
            scale=(max if s['fit']=='cover' else min)(w/source.width,h/source.height)*zoom
            scaled=source.resize((max(1,round(source.width*scale)),max(1,round(source.height*scale))),Image.Resampling.BILINEAR)
            image.paste(scaled,(round((w-scaled.width)*s['panX']),round((h-scaled.height)*s['panY'])))
            if s['blur']:image=image.filter(ImageFilter.GaussianBlur(s['blur']*u/720))
            image=Image.blend(image,Image.new('RGB',(w,h),s['background']),s['dim'])
        if s['vignette']:image.paste(Image.new('RGB',(w,h),'black'),(0,0),self.vignette)
        layer=Image.new('RGBA',(w,h));draw=ImageDraw.Draw(layer);accent=rgb(s['color']);second=rgb(s['color2'])
        cx,cy=w*s['logoX'],h*s['logoY'];radius=u*.19*s['logoSize']*(1+(low*.13+beat*.03)*strength*s['pulse']);angle=t*s['rotation']*.7
        if s['preset']=='vinyl':
            for i in range(14):
                r=radius*(1.03+i*.025);draw.ellipse((cx-r,cy-r,cx+r,cy+r),outline=(*mix(accent,second,i/14),76),width=max(1,round(u*.001)))
        if s['preset']=='tunnel':
            for i in range(9):
                phase=(i/9+t*.035)%1;r=u*(.12+phase*.85)
                points=[(cx+math.cos(j/6*math.tau+angle*.2)*r,cy+math.sin(j/6*math.tau+angle*.2)*r) for j in range(7)]
                draw.line(points,fill=(*mix(accent,second,phase),round((.15+.4*(1-phase))*255)),width=max(1,round(u*.002*(1+beat))))
        if s['preset']=='aurora':
            for i in range(5):
                points=[(w*j/64,h*(.25+i*.09)+math.sin(j/64*math.tau+t*.3+i)*u*(.06+low*.035)) for j in range(65)]
                draw.line(points,fill=(*mix(accent,second,i/4),31),width=max(1,round(u*(.025+mid*.025))),joint='curve')
        if s['preset']=='grid':
            horizon=h*.55;color=(*second,102);line_width=max(1,round(u*.002))
            for i in range(-8,9):draw.line((w/2+i*w*.035,horizon,w/2+i*w*.2,h),fill=color,width=line_width)
            for i in range(12):
                q=(i/12+t*.08)%1;y=horizon+q*q*(h-horizon);draw.line((0,y,w,y),fill=color,width=line_width)
        if s['preset']=='liquid':
            for i in range(5):
                px=w*(.5+.4*math.sin(t*.15+i));py=h*(.5+.4*math.cos(t*.13+i));r=u*(.08+.04*mid)
                draw.ellipse((px-r,py-r,px+r,py+r),fill=(*mix(accent,second,i/5),30))
        if s['preset']=='stage':
            for i in range(5):
                x=w*(i/4);draw.polygon([(cx,h*.1),(x-u*.1,h),(x+u*.1,h)],fill=(*mix(accent,second,i/5),round(12+20*low)))
        if s['particles']!='none':
            for i in range(int(s['particleCount'])):
                phase=rand(i,s['seed']);a=rand(i+400,s['seed'])*math.tau+t*.05
                if s['particles']=='snow':px=rand(i+20,s['seed'])*w;py=(phase*h+t*22)%h
                else:
                    distance=(phase*u*.8+t*18)%(u*.8);px=cx+math.cos(a)*distance;py=cy+math.sin(a)*distance
                size=(1+rand(i+800,s['seed'])*2+high*2)*u/720
                color=(*mix(accent,second,phase),round(90+130*phase))
                draw.ellipse((px-size,py-size,px+size,py+size),fill=color)
                if s['particles']=='stars':draw.line((px-size*2,py,px+size*2,py),fill=color,width=1);draw.line((px,py-size*2,px,py+size*2),fill=color,width=1)
        bars=features[5:]
        if s['spectrum']=='ring':
            for i,energy in enumerate(bars):
                a=i/BANDS*math.tau-math.pi/2;inner=radius+u*.018;outer=inner+float(energy)*u*.11*strength*s['spectrumSize']
                draw.line((cx+math.cos(a)*inner,cy+math.sin(a)*inner,cx+math.cos(a)*outer,cy+math.sin(a)*outer),fill=(*mix(accent,second,i/BANDS),235),width=max(2,round(u*.005)))
        elif s['spectrum']=='bars':
            for i,energy in enumerate(bars):
                x=w*.12+i*w*.76/BANDS;height=u*.025+float(energy)*u*.17*strength*s['spectrumSize']
                draw.rounded_rectangle((x,h*s['spectrumY']-height,x+w*.76/BANDS*.6,h*s['spectrumY']),radius=2,fill=(*mix(accent,second,i/BANDS),230))
        elif s['spectrum']=='wave':
            points=[(w*.1+i*w*.8/(BANDS-1),h*(s['spectrumY']-.05)+math.sin(i*.55+t*2)*float(energy)*u*.09*strength*s['spectrumSize']) for i,energy in enumerate(bars)]
            draw.line(points,fill=(*accent,240),width=max(2,round(u*.005)),joint='curve')
        elif s['spectrum']=='mirror':
            for i,energy in enumerate(bars):
                x=w*.12+i*w*.76/BANDS;height=u*.012+float(energy)*u*.085*strength*s['spectrumSize']
                draw.rectangle((x,h*s['spectrumY']-height,x+w*.76/BANDS*.6,h*s['spectrumY']+height),fill=(*mix(accent,second,i/BANDS),230))
        if s['shape']!='none':
            mask=Image.new('L',(round(radius*2),round(radius*2)));md=ImageDraw.Draw(mask);r=radius-2
            if s['shape']=='circle':md.ellipse((1,1,2*r,2*r),fill=255)
            else:
                n=3 if s['shape']=='triangle' else 4
                points=[(radius+math.cos(angle-math.pi/2+j*math.tau/n)*r,radius+math.sin(angle-math.pi/2+j*math.tau/n)*r) for j in range(n)]
                md.polygon(points,fill=255)
            fill=ImageOps.fit(self.logo,mask.size) if self.logo is not None else Image.new('RGBA',mask.size,(*rgb(s['background']),240))
            if self.logo is not None and s['spinLogo']:fill=fill.rotate(-math.degrees(angle),resample=Image.Resampling.BICUBIC)
            layer.paste(fill,(round(cx-radius),round(cy-radius)),mask)
            if s['shape']=='circle':draw.ellipse((cx-radius,cy-radius,cx+radius,cy+radius),outline=(*accent,255),width=max(2,round(u*.004)))
            else:
                n=3 if s['shape']=='triangle' else 4
                points=[(cx+math.cos(angle-math.pi/2+j*math.tau/n)*r,cy+math.sin(angle-math.pi/2+j*math.tau/n)*r) for j in range(n)]
                draw.line(points+[points[0]],fill=(*accent,255),width=max(2,round(u*.004)),joint='curve')
        image=image.convert('RGBA')
        if s['glow']:
            glow=layer.filter(ImageFilter.GaussianBlur(max(1,u*.01)));glow.putalpha(glow.getchannel('A').point(lambda a:int(a*s['glow']*.6)))
            image=Image.alpha_composite(image,glow)
        image=Image.alpha_composite(image,layer);draw=ImageDraw.Draw(image)
        if s['preset']=='retro':
            for y in range(0,h,max(3,round(u*.006))):draw.line((0,y,w,y),fill=(0,0,0,35))
        for text,y,face in [(s['title'],h*s['textY'],self.titlefont),(s['subtitle'],h*min(.97,s['textY']+.06),self.subfont)]:
            if text:
                face=font(face.size*s['textSize'])
                width=draw.textlength(text,font=face)
                if width>w*.9:face=font(face.size*w*.9/width)
                draw.text((w/2,y),text,font=face,anchor='mm',fill=s['textColor'],stroke_width=max(1,round(u/720)),stroke_fill='#000000')
        if s['lyricsOn'] and self.lyrics:
            index=bisect.bisect_right(self.lyric_times,s['start']+t-s['lyricsOffset'])-1
            if 0<=index<len(self.lyrics) and self.lyrics[index]['text']:
                cy=h*s['lyricsY'];size=u*.034*s['lyricsSize'];linefont=font(size*(1+float(beat)*.08 if s['lyricsStyle']=='pulse' else 1))
                panel=Image.new('RGBA',(w,h));pd=ImageDraw.Draw(panel);pd.rounded_rectangle((w*.06,cy-size*2.5,w*.94,cy+size*2.5),radius=round(size*.4),fill=(0,0,0,175))
                image=Image.alpha_composite(image,panel);draw=ImageDraw.Draw(image)
                for offset in (-1,0,1):
                    if not 0<=index+offset<len(self.lyrics):continue
                    text=self.lyrics[index+offset]['text'];face=linefont if offset==0 else font(size*.72)
                    width=draw.textlength(text,font=face)
                    if width>w*.84:face=font(max(size*.48,face.size*w*.84/width))
                    while text and draw.textlength(text,font=face)>w*.84:text=text[:-2]+'…'
                    active=rgb(s['textColor'])
                    if s['lyricsStyle']=='fade':active=mix((126,138,152),active,min(1,max(0,(s['start']+t-s['lyricsOffset']-self.lyrics[index]['at'])/.4)))
                    draw.text((w/2,cy+offset*size*1.55),text,font=face,anchor='mm',fill=active if offset==0 else '#a3acb7',stroke_width=1,stroke_fill='#000000')
        opacity=min(1,t/min(s['fadeIn'],self.duration/2)) if s['fadeIn'] else 1
        if s['fadeOut']:opacity=min(opacity,max(0,(self.duration-t)/min(s['fadeOut'],self.duration/2)))
        image=image.convert('RGB')
        return Image.blend(Image.new('RGB',(w,h),'black'),image,opacity) if opacity<1 else image

def render(folder):
    folder=Path(folder);s=validate(json.loads((folder/'scene.json').read_text(encoding='utf-8')))
    metadata=json.loads((folder/'analysis.json').read_text());start=s['start'];end=min(s['end'] or metadata['duration'],metadata['duration'])
    if not start<end:raise ValueError('Selected interval is outside audio')
    scene=Scene(folder,s);w,h=scene.w,scene.h;fps=s['fps'];count=math.ceil((end-start)*fps)
    audio_filters=[]
    if s['fadeIn']:audio_filters.append(f"afade=t=in:d={min(s['fadeIn'],(end-start)/2)}")
    if s['fadeOut']:
        length=min(s['fadeOut'],(end-start)/2);audio_filters.append(f'afade=t=out:st={end-start-length}:d={length}')
    features=np.load(folder/'features.npy',mmap_mode='r');background=None
    stderr=open(folder/'render.log','wb')
    encoder=subprocess.Popen([ffmpeg(),'-nostdin','-hide_banner','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{w}x{h}','-r',str(fps),'-i','pipe:0',
        '-ss',str(start),'-protocol_whitelist','file,pipe','-i',str(folder/'audio.input'),'-map','0:v','-map','1:a:0','-t',str(end-start),*(['-af',','.join(audio_filters)] if audio_filters else []),'-c:v','libx264','-preset','veryfast','-crf','21','-pix_fmt','yuv420p','-threads','1','-c:a','aac','-b:a','192k','-movflags','+faststart',str(folder/'result.pending.mp4')],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    try:
        if s['backgroundKind']=='video' and (folder/'background.input').exists():
            with Image.open(folder/'background-poster.png') as poster:pw,ph=poster.size
            factor=min(max(w/pw,h/ph),3840/pw,3840/ph);bw=max(2,round(pw*factor/2)*2);bh=max(2,round(ph*factor/2)*2)
            background=subprocess.Popen([ffmpeg(),'-nostdin','-hide_banner','-v','error','-stream_loop','-1','-protocol_whitelist','file,pipe','-i',str(folder/'background.input'),'-an','-vf',f'fps={fps},scale={bw}:{bh}','-threads','1','-f','rawvideo','-pix_fmt','rgb24','pipe:1'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        progress(folder,'render',0)
        for index in range(count):
            if index%fps==0 and shutil.disk_usage(folder).free<512*1024**2:raise OSError('Not enough video workspace')
            frame=None
            if background:
                body=bytearray()
                while len(body)<bw*bh*3:
                    chunk=background.stdout.read(bw*bh*3-len(body))
                    if not chunk:raise ValueError('Video background decode failed')
                    body.extend(chunk)
                frame=Image.frombytes('RGB',(bw,bh),bytes(body))
            t=index/fps;encoder.stdin.write(scene.frame(t,sample(features,start+t),frame).tobytes())
            if index%max(1,fps//2)==0:progress(folder,'render',index/count)
        encoder.stdin.close()
        if encoder.wait()!=0:raise ValueError('Video encoding failed')
        os.replace(folder/'result.pending.mp4',folder/'result.mp4');progress(folder,'complete',1)
    finally:
        if encoder.poll() is None:encoder.kill();encoder.wait()
        if background and background.poll() is None:background.kill();background.wait()
        if background and background.stdout:background.stdout.close()
        if encoder.stdin and not encoder.stdin.closed:encoder.stdin.close()
        stderr.close()
        (folder/'result.pending.mp4').unlink(missing_ok=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['analyse','assets','render']);parser.add_argument('folder',type=Path);args=parser.parse_args()
    try:({'analyse':analyse,'assets':analyse_assets,'render':render}[args.action])(args.folder)
    except Exception:
        progress(args.folder,'failed',0)
        raise
