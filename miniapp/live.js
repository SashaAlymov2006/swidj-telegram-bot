// Native, bounded Web Audio audition. No models or network calls.
export const liveEffects=new Set(['reverb','pro_reverb','echo','delay','lofi','compressor','equalizer','highpass','lowpass','stereo','distortion','tremolo']);
export const dspDefaults={eq60:0,eq250:0,eq1000:5,eq4000:0,eq12000:0,lofi_hz:2000,highpass_hz:3000,lowpass_hz:300,delay_ms:250,feedback:.15,room_s:1.1,comp_threshold:-26,comp_ratio:4,comp_attack:10,comp_release:100,stereo_width:1,tremolo_rate:5,tremolo_depth:.5,drive:2};
const impulses=new WeakMap();
function impulse(context,wide,seconds){
 let cache=impulses.get(context);if(!cache){cache={};impulses.set(context,cache);}
 const key=`${wide}:${seconds}`;if(cache[key])return cache[key];
 if(Object.keys(cache).length>=6)delete cache[Object.keys(cache)[0]];
 const length=Math.floor(context.sampleRate*seconds*(wide?1.8:1)),buffer=context.createBuffer(2,length,context.sampleRate);let seed=42;
 for(let channel=0;channel<2;channel++){const samples=buffer.getChannelData(channel);for(let i=0;i<length;i++){seed=(seed*1664525+1013904223)>>>0;samples[i]=(seed/2147483648-1)*Math.pow(1-i/length,wide?2:3);}}
 cache[key]=buffer;return buffer;
}
export function connectLive(context,input,output,effects,ambience=100,settings={}){
 const nodes=[],wetNodes=[],updaters=[],oscillators=[];const entry=context.createGain(),exit=context.createGain();input.connect(entry);let tail=entry;const params={...dspDefaults,...settings};
 const keep=node=>{nodes.push(node);return node;};
 const smooth=(parameter,value)=>parameter.setTargetAtTime(value,context.currentTime,.03);
 const filter=(type,frequency,gain=0,key=null,gainKey=null)=>{const n=keep(context.createBiquadFilter());n.type=type;n.frequency.value=frequency;n.gain.value=gain;tail.connect(n);tail=n;if(key)updaters.push(p=>smooth(n.frequency,p[key]));if(gainKey)updaters.push(p=>smooth(n.gain,p[gainKey]));};
 for(const effect of effects){
  if(!liveEffects.has(effect))continue;
  if(effect==='lofi'){filter('highpass',150);filter('lowpass',params.lofi_hz,0,'lofi_hz');}
  else if(effect==='highpass')filter('highpass',params.highpass_hz,0,'highpass_hz');
  else if(effect==='lowpass')filter('lowpass',params.lowpass_hz,0,'lowpass_hz');
  else if(effect==='equalizer'){for(const hz of [60,250,1000,4000,12000])filter('peaking',hz,params['eq'+hz],null,'eq'+hz);}
  else if(effect==='compressor'){
   const n=keep(context.createDynamicsCompressor());n.knee.value=6;
   const update=p=>{smooth(n.threshold,p.comp_threshold);smooth(n.ratio,p.comp_ratio);smooth(n.attack,p.comp_attack/1000);smooth(n.release,p.comp_release/1000);};update(params);updaters.push(update);tail.connect(n);tail=n;
  }else if(effect==='distortion'){
   const n=keep(context.createWaveShaper());n.oversample='2x';let lastDrive;const update=p=>{if(p.drive===lastDrive)return;lastDrive=p.drive;const curve=new Float32Array(2048);for(let i=0;i<curve.length;i++)curve[i]=Math.tanh((i*2/(curve.length-1)-1)*p.drive);n.curve=curve;};update(params);updaters.push(update);tail.connect(n);tail=n;
  }else if(effect==='tremolo'){
   const n=keep(context.createGain()),osc=keep(context.createOscillator()),depth=keep(context.createGain());oscillators.push(osc);
   const update=p=>{smooth(osc.frequency,p.tremolo_rate);smooth(n.gain,1-p.tremolo_depth/2);smooth(depth.gain,p.tremolo_depth/2);};update(params);updaters.push(update);osc.connect(depth).connect(n.gain);osc.start();tail.connect(n);tail=n;
  }else if(effect==='stereo'){
   const stereo=keep(context.createGain());stereo.channelCount=2;stereo.channelCountMode='explicit';
   const split=keep(context.createChannelSplitter(2)),merge=keep(context.createChannelMerger(2));tail.connect(stereo).connect(split);
   for(let channel=0;channel<2;channel++)for(let target=0;target<2;target++){const n=keep(context.createGain());split.connect(n,channel);n.connect(merge,0,target);const update=p=>smooth(n.gain,(channel===target?1+p.stereo_width:1-p.stereo_width)/2);update(params);updaters.push(update);}tail=merge;
  }else{
   const mix=keep(context.createGain()),dry=keep(context.createGain()),wet=keep(context.createGain());dry.gain.value=.8;const amount=effect==='delay'?.4:.3;wet.gain.value=amount*ambience/100;wetNodes.push({wet,amount});tail.connect(dry).connect(mix);
   if(effect==='reverb'||effect==='pro_reverb'){
    const n=keep(context.createConvolver());n.buffer=impulse(context,effect==='pro_reverb',params.room_s);tail.connect(n).connect(wet).connect(mix);
   }else{
    const delay=keep(context.createDelay(2)),feedback=keep(context.createGain());delay.delayTime.value=params.delay_ms/1000;feedback.gain.value=params.feedback;
    updaters.push(p=>{smooth(delay.delayTime,p.delay_ms/1000);smooth(feedback.gain,p.feedback);});tail.connect(delay).connect(wet).connect(mix);delay.connect(feedback).connect(delay);
   }tail=mix;
  }
 }
 tail.connect(exit);exit.connect(output);
 const cleanup=()=>{try{input.disconnect(entry);}catch{}entry.disconnect();exit.disconnect();for(const osc of oscillators)try{osc.stop();}catch{}for(const n of nodes)n.disconnect();};
 cleanup.gain=exit.gain;
 cleanup.setAmbience=value=>wetNodes.forEach(({wet,amount})=>smooth(wet.gain,amount*value/100));
 cleanup.setParams=value=>updaters.forEach(update=>update({...dspDefaults,...value}));return cleanup;
}
