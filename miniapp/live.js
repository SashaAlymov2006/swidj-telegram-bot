// Small native Web Audio graphs: no AI, uploads, decoding of a full track or extra libraries.
export const liveEffects = new Set(['reverb','pro_reverb','echo','delay','lofi','compressor','equalizer','highpass','lowpass']);
const impulses=new WeakMap();
function impulse(context,wide){
  let cache=impulses.get(context);if(!cache){cache={};impulses.set(context,cache);}
  const key=wide?'wide':'room';if(cache[key])return cache[key];
  const length=Math.floor(context.sampleRate*(wide?2.4:1.1)),buffer=context.createBuffer(2,length,context.sampleRate);
  let seed=42;
  for(let channel=0;channel<2;channel++){const samples=buffer.getChannelData(channel);for(let i=0;i<length;i++){seed=(seed*1664525+1013904223)>>>0;samples[i]=(seed/2147483648-1)*Math.pow(1-i/length,wide?2:3);}}
  cache[key]=buffer;return buffer;
}
export function connectLive(context,input,output,effects,ambience=100){
  input.disconnect();const nodes=[],wetNodes=[];
  const keep=node=>{nodes.push(node);return node;};
  let tail=input;
  const filter=(type,frequency,gain=0)=>{const node=keep(context.createBiquadFilter());node.type=type;node.frequency.value=frequency;node.gain.value=gain;tail.connect(node);tail=node;};
  for(const effect of effects){
    if(!liveEffects.has(effect))continue;
    if(effect==='lofi'){filter('highpass',150);filter('lowpass',2000);}
    else if(effect==='highpass')filter('highpass',3000);
    else if(effect==='lowpass')filter('lowpass',300);
    else if(effect==='equalizer')filter('peaking',1000,5);
    else if(effect==='compressor'){
      const node=keep(context.createDynamicsCompressor());node.threshold.value=-26;node.knee.value=6;node.ratio.value=4;tail.connect(node);tail=node;
    } else {
      const mix=keep(context.createGain()),dry=keep(context.createGain()),wet=keep(context.createGain());
      dry.gain.value=.8;const amount=effect==='delay'?.4:.3;wet.gain.value=amount*ambience/100;wetNodes.push({wet,amount});
      tail.connect(dry).connect(mix);
      if(effect==='reverb'||effect==='pro_reverb'){
        const convolver=keep(context.createConvolver());convolver.buffer=impulse(context,effect==='pro_reverb');tail.connect(convolver).connect(wet).connect(mix);
      }else{
        const delay=keep(context.createDelay(1)),feedback=keep(context.createGain());delay.delayTime.value=effect==='delay'?.36:.25;feedback.gain.value=effect==='delay'?.3:.15;
        tail.connect(delay).connect(wet).connect(mix);delay.connect(feedback).connect(delay);
      }
      tail=mix;
    }
  }
  tail.connect(output);
  const cleanup=()=>{input.disconnect();for(const node of nodes)node.disconnect();};
  cleanup.setAmbience=value=>wetNodes.forEach(({wet,amount})=>wet.gain.setTargetAtTime(amount*value/100,context.currentTime,.03));
  return cleanup;
}
