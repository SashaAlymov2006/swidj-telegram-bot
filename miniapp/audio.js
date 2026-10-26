import {connectLive,dspDefaults} from './live.js';
// Browser audio stays on the user's device. No microphone access or uploads.
export function stamp(value) {
  const seconds = Math.max(0, Math.floor(Number(value) || 0));
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
}

export function wavBlob(buffer) {
  const channels = Math.min(buffer.numberOfChannels, 2), length = buffer.length;
  const data = new ArrayBuffer(44 + length * channels * 2), view = new DataView(data);
  const text = (offset, value) => [...value].forEach((c, i) => view.setUint8(offset + i, c.charCodeAt(0)));
  text(0, 'RIFF'); view.setUint32(4, 36 + length * channels * 2, true); text(8, 'WAVE'); text(12, 'fmt ');
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, channels, true);
  view.setUint32(24, buffer.sampleRate, true); view.setUint32(28, buffer.sampleRate * channels * 2, true);
  view.setUint16(32, channels * 2, true); view.setUint16(34, 16, true); text(36, 'data');
  view.setUint32(40, length * channels * 2, true);
  const samples = Array.from({length: channels}, (_, c) => buffer.getChannelData(c));
  let cursor = 44;
  for (let i = 0; i < length; i++) for (let c = 0; c < channels; c++) {
    const sample = Math.max(-1, Math.min(1, samples[c][i]));
    view.setInt16(cursor, sample < 0 ? sample * 32768 : sample * 32767, true); cursor += 2;
  }
  return new Blob([data], {type: 'audio/wav'});
}

export function chain(context, source, destination, bass, treble = 0) {
  const headroom = context.createGain();
  headroom.gain.value = 10 ** (-(Math.max(0, bass)+Math.max(0, treble)) / 20);
  const filter = context.createBiquadFilter(); filter.type = 'lowshelf'; filter.frequency.value = 100; filter.gain.value = bass;
  const high = context.createBiquadFilter(); high.type = 'highshelf'; high.frequency.value = 3000; high.gain.value = treble;
  const compressor = context.createDynamicsCompressor();
  compressor.threshold.value = -2; compressor.knee.value = 0; compressor.ratio.value = 20;
  compressor.attack.value = .002; compressor.release.value = .1;
  const master=context.createGain();
  source.connect(headroom).connect(filter).connect(high).connect(compressor).connect(master).connect(destination);
  return {headroom, filter, high, compressor, master};
}

export class AudioEngine {
  constructor(element,{mobile=globalThis.matchMedia?.('(pointer: coarse)').matches||false}={}) {
    this.element=element;
    this.mobile=mobile;
    const agent=globalThis.navigator?.userAgent||'';
    this.webkit=/AppleWebKit/.test(agent)&&!/(Chrome|Chromium|Edg|OPR)\//.test(agent);
    this.rateAt=-Infinity;
    this.bass=0;this.speed=1;this.treble=0;this.pitch=0;
    this.bypass=false;this.processed=false;this.linked=false;
    this.trimStart=0;this.trimEnd=0;this.fade=0;
    this.effects=[];this.params={...dspDefaults};this.ambience=100;
  }
  async unlock() {
    if (!this.context) {
      this.context = new AudioContext({latencyHint:this.mobile?'playback':'interactive'});
      this.source=this.context.createMediaElementSource(this.element);
      this.nodes = chain(this.context, this.source, this.context.destination, this.bypass?0:this.bass, this.bypass?0:this.treble);
      this.nodes.high.disconnect(this.nodes.compressor);
      this.rebuildLive();
      this.element.addEventListener('emptied',()=>this.resetPitch());
      this.pitchReady=this.initializePitch();
    }
    await this.context.resume();
    await this.pitchReady;
  }
  async initializePitch(){
    if(!this.context.audioWorklet)return;
    let node;
    try{
      const {SoundTouchNode}=await import('./SoundTouchNode.js');
      await SoundTouchNode.register(this.context,new URL('./soundtouch-processor.js',import.meta.url).href);
      node=new SoundTouchNode({context:this.context});
      node.setStretchParameters({sequenceMs:80,seekWindowMs:20,overlapMs:8,quickSeek:true});
      this.source.disconnect(this.nodes.headroom);this.source.connect(node).connect(this.nodes.headroom);
      this.pitchNode=node;this.livePitch=true;this.setSpeed(this.speed);
      node.onprocessorerror=()=>{
        try{this.source.disconnect(node);node.disconnect();this.source.connect(this.nodes.headroom);}catch{}
        this.pitchNode=null;this.livePitch=false;this.setSpeed(this.speed);
        globalThis.dispatchEvent?.(new Event('swidj-pitch-fallback'));
      };
    }catch{
      if(node){try{this.source.disconnect(node);node.disconnect();this.source.connect(this.nodes.headroom);}catch{}}
      this.livePitch=false;
    } // Existing server processing remains the compatibility path.
  }
  resetPitch(){this.pitchNode?.port.postMessage({type:'swidj-reset'});}
  setPitch(value){this.pitch=Number(value)||0;this.syncPitch();}
  syncPitch(){
    if(!this.pitchNode)return;
    const rate=this.element.playbackRate,neutral=this.bypass||this.processed;
    const desired=neutral?1:this.linked?rate:2**((this.pitch||0)/12);
    // Native tempo preserves input pitch. The worklet shifts that stable-pitch
    // stream, avoiding browser-dependent resampling/preservesPitch=false behavior.
    if(this.pitchRate!==1){this.pitchNode.playbackRate.value=1;this.pitchRate=1;}
    if(this.pitchTarget!==desired){
      const param=this.pitchNode.pitch,now=this.context.currentTime;
      if(param.cancelAndHoldAtTime)param.cancelAndHoldAtTime(now);else param.cancelScheduledValues(now);
      if(neutral)param.setValueAtTime(desired,now);else param.setTargetAtTime(desired,now,.02);
      this.pitchTarget=desired;
    }
  }
  rebuildLive(){
    if(!this.nodes)return;
    clearTimeout(this.rackTimer);
    const previous=this.disconnectLive,now=this.context.currentTime;
    const next=connectLive(this.context,this.nodes.high,this.nodes.compressor,this.bypass||this.processed?[]:this.effects,this.ambience,this.params);
    this.disconnectLive=next;
    if(previous){
      next.gain.setValueAtTime(0,now);next.gain.linearRampToValueAtTime(1,now+.045);
      if(previous.gain.cancelAndHoldAtTime)previous.gain.cancelAndHoldAtTime(now);
      else {previous.gain.cancelScheduledValues(now);previous.gain.setValueAtTime(previous.gain.value,now);}
      previous.gain.linearRampToValueAtTime(0,now+.045);
      setTimeout(previous,100);
    }
  }
  setLinked(value){this.linked=value;this.setSpeed(this.speed);}
  setParams(values){const room=values.room_s??this.params.room_s;const oldRoom=this.params.room_s;Object.assign(this.params,values);if(room!==oldRoom){clearTimeout(this.rackTimer);this.rackTimer=setTimeout(()=>this.rebuildLive(),160);}else this.disconnectLive?.setParams?.(this.params);}
  setEffects(effects){this.effects=[...effects];this.rebuildLive();}
  setAmbience(value){this.ambience=value;this.disconnectLive?.setAmbience?.(value);}
  setProcessed(value){if(this.processed===value)return;this.processed=value;this.rebuildLive();this.applyTone();this.setSpeed(this.speed);}
  applyTone() {
    if(!this.nodes)return;
    const bass=this.bypass||this.processed?0:this.bass,treble=this.bypass||this.processed?0:this.treble;
    this.nodes.headroom.gain.setTargetAtTime(10**(-(Math.max(0,bass)+Math.max(0,treble))/20),this.context.currentTime,.03);
    this.nodes.filter.gain.setTargetAtTime(bass,this.context.currentTime,.03);
    this.nodes.high.gain.setTargetAtTime(treble,this.context.currentTime,.03);
  }
  setBass(value){this.bass=value;this.applyTone();}
  setTreble(value){this.treble=value;this.applyTone();}
  setBypass(value){if(this.bypass===value)return;this.bypass=value;this.rebuildLive();this.applyTone();this.setSpeed(this.speed);}
  setSpeed(value) {
    this.speed = value;
    const rate=this.bypass||this.processed?1:value;
    // Keep live tempo independent of pitch, matching server exports.
    const preserve=this.livePitch||!this.linked;
    if(this.element.preservesPitch!==preserve)this.element.preservesPitch=preserve;
    if('webkitPreservesPitch' in this.element&&this.element.webkitPreservesPitch!==preserve)this.element.webkitPreservesPitch=preserve;
    this.pendingRate=rate;
    clearTimeout(this.rateTimer);
    const delay=this.mobile||this.webkit?Math.max(0,40-(performance.now()-this.rateAt)):0;
    if(delay)this.rateTimer=setTimeout(()=>this.flushRate(),delay);else this.flushRate();
  }
  flushRate(){clearTimeout(this.rateTimer);if(this.pendingRate!==undefined&&Math.abs(this.element.playbackRate-this.pendingRate)>.000001)this.element.playbackRate=this.pendingRate;this.rateAt=performance.now();this.syncPitch();}
  fadeOutput(value,seconds=.035){
    const gain=this.nodes?.master?.gain;if(!gain)return;
    const now=this.context.currentTime;
    if(gain.cancelAndHoldAtTime)gain.cancelAndHoldAtTime(now);else gain.cancelScheduledValues(now);
    gain.linearRampToValueAtTime(value,now+seconds);
  }
  cancelSourceSwitch(){this.sourceSwitch=(this.sourceSwitch||0)+1;this.fadeOutput(1);}
  async switchSource(url,{position=0,playing=false,valid=()=>true}={}){
    const revision=(this.sourceSwitch||0)+1;this.sourceSwitch=revision;
    const audio=this.element,started=performance.now();
    const active=()=>revision===this.sourceSwitch;
    const waitFor=(events,ready)=>new Promise((resolve,reject)=>{
      if(ready()){resolve();return;}
      let timeout;
      const clean=()=>{clearTimeout(timeout);for(const event of events)audio.removeEventListener(event,check);audio.removeEventListener('error',failed);};
      const check=()=>{if(!active()||ready()){clean();resolve();}};
      const failed=()=>{clean();if(active())reject(new Error('invalidAudio'));else resolve();};
      for(const event of events)audio.addEventListener(event,check);
      audio.addEventListener('error',failed);
      timeout=setTimeout(()=>{clean();if(active())reject(new Error('invalidAudio'));else resolve();},15000);
    });
    this.fadeOutput(0,.015);
    try{
      await new Promise(resolve=>setTimeout(resolve,20));
      if(!active()||!valid())return false;
      audio.pause();audio.src=url;
      await waitFor(['loadedmetadata'],()=>audio.readyState>=1);
      if(!active())return false;
      const elapsed=playing?(performance.now()-started)/1000*this.speed:0;
      audio.currentTime=Math.max(0,Math.min(position+elapsed,Number.isFinite(audio.duration)?Math.max(0,audio.duration-.01):position+elapsed));
      await waitFor(['seeked','canplay'],()=>!audio.seeking&&audio.readyState>=2);
      if(!active())return false;
      this.flushRate();
      if(playing)await audio.play();
      return true;
    }finally{if(active())this.fadeOutput(1,.04);}
  }
  async render(blob, preview = false, sourceDuration = this.element.duration) {
    const bass = this.bypass?0:this.bass, treble=this.bypass?0:this.treble, speed = this.bypass?1:this.speed;
    if (!Number.isFinite(sourceDuration) || sourceDuration > 180) throw new Error('long');
    const trimStart=this.trimStart,trimEnd=this.trimEnd,fadeSeconds=this.fade;
    await this.unlock();
    const input = await this.context.decodeAudioData(await blob.arrayBuffer());
    // Bound mobile memory. Long/full MP3 processing remains available in the bot.
    if (input.duration > 180) throw new Error('long');
    const start=Math.min(Math.max(0,trimStart),input.duration);
    const end=trimEnd>0?Math.min(trimEnd,input.duration):input.duration;
    if(end<=start)throw new Error('invalidTrim');
    if(!preview&&(end-start)/speed>180)throw new Error('long');
    const duration = Math.min((end-start) / speed, preview ? 15 : 180);
    const rate = 44100;
    const offline = new OfflineAudioContext(Math.min(input.numberOfChannels, 2), Math.ceil(duration * rate), rate);
    const source = offline.createBufferSource(); source.buffer = input; source.playbackRate.value = speed;
    const envelope=offline.createGain();envelope.connect(offline.destination);
    const fade=Math.min(fadeSeconds,duration/2);
    if(fade>0){envelope.gain.setValueAtTime(0,0);envelope.gain.linearRampToValueAtTime(1,fade);envelope.gain.setValueAtTime(1,duration-fade);envelope.gain.linearRampToValueAtTime(0,duration);}
    chain(offline, source, envelope, bass, treble); source.start(0,start,Math.min(end-start,duration*speed));
    return wavBlob(await offline.startRendering());
  }
}
