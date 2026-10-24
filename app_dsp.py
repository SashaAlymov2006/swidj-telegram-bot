"""Validated app-studio parameters; no caller-supplied filter expressions."""
import math
SCHEMA={
 'eq60':(0,-12,12),'eq250':(0,-12,12),'eq1000':(5,-12,12),'eq4000':(0,-12,12),'eq12000':(0,-12,12),
 'lofi_hz':(2000,500,3500),'highpass_hz':(3000,20,6000),'lowpass_hz':(300,100,20000),
 'delay_ms':(250,60,1000),'feedback':(.15,0,.65),'room_s':(1.1,.2,3),
 'comp_threshold':(-26,-48,-6),'comp_ratio':(4,1,12),'comp_attack':(10,1,100),'comp_release':(100,20,1000),
 'stereo_width':(1,0,2),'tremolo_rate':(5,.5,12),'tremolo_depth':(.5,0,1),'drive':(2,1,8),
}
def parameters(settings):
 raw=settings.get('params',{})
 if not isinstance(raw,dict) or any(key not in SCHEMA for key in raw):raise ValueError('Invalid parameter')
 result={}
 for key,(default,low,high) in SCHEMA.items():
  value=raw.get(key,default)
  if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not low<=value<=high:raise ValueError('Invalid parameter')
  result[key]=value
 return result

def effect_filter(effect,p,ambience):
 if effect=='equalizer':return ','.join(f'equalizer=f={hz}:t=o:w=1:g={p["eq"+str(hz)]}' for hz in (60,250,1000,4000,12000))
 if effect=='lofi':return f'aresample=8000,lowpass=f={p["lofi_hz"]},highpass=f=150,aresample=44100'
 if effect=='highpass':return f'highpass=f={p["highpass_hz"]}'
 if effect=='lowpass':return f'lowpass=f={p["lowpass_hz"]}'
 if effect=='compressor':return f'acompressor=threshold={10**(p["comp_threshold"]/20)}:ratio={p["comp_ratio"]}:attack={p["comp_attack"]}:release={p["comp_release"]}'
 if effect in ('reverb','pro_reverb'):
  delay=min(5000,p['room_s']*1000*(1.8 if effect=='pro_reverb' else 1))
  return f'aecho=0.8:0.8:{delay*.07}|{delay*.13}:{.25*ambience}|{.15*ambience}'
 if effect in ('echo','delay'):
  delay=p['delay_ms'];feedback=p['feedback']
  return f'aecho=0.8:0.8:{delay}|{delay*2}|{delay*3}:{.4*ambience}|{feedback*ambience}|{feedback**2*ambience}'
 if effect=='tremolo':return f'tremolo=f={p["tremolo_rate"]}:d={p["tremolo_depth"]}'
 if effect=='distortion':return f'volume={p["drive"]},asoftclip=type=tanh'
 if effect=='stereo':
  a=(1+p['stereo_width'])/2;b=(1-p['stereo_width'])/2
  return f'aformat=channel_layouts=stereo,pan=stereo|c0={a}*c0{b:+g}*c1|c1={b}*c0+{a}*c1'
 return None
