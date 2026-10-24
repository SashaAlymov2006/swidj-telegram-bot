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
  source.connect(headroom).connect(filter).connect(high).connect(compressor).connect(destination);
  return {headroom, filter, high};
}

export class AudioEngine {
  constructor(element) { this.element = element; this.bass = 0; this.speed = 1; this.treble=0; this.bypass=false; this.trimStart=0; this.trimEnd=0; this.fade=0; }
  async unlock() {
    if (!this.context) {
      this.context = new AudioContext();
      this.nodes = chain(this.context, this.context.createMediaElementSource(this.element), this.context.destination, this.bypass?0:this.bass, this.bypass?0:this.treble);
    }
    await this.context.resume();
  }
  applyTone() {
    if(!this.nodes)return;
    const bass=this.bypass?0:this.bass,treble=this.bypass?0:this.treble;
    this.nodes.headroom.gain.setTargetAtTime(10**(-(Math.max(0,bass)+Math.max(0,treble))/20),this.context.currentTime,.03);
    this.nodes.filter.gain.setTargetAtTime(bass,this.context.currentTime,.03);
    this.nodes.high.gain.setTargetAtTime(treble,this.context.currentTime,.03);
  }
  setBass(value){this.bass=value;this.applyTone();}
  setTreble(value){this.treble=value;this.applyTone();}
  setBypass(value){this.bypass=value;this.applyTone();this.setSpeed(this.speed);}
  setSpeed(value) {
    this.speed = value; this.element.playbackRate = this.bypass?1:value;
    // Match offline export: changing speed also changes pitch.
    this.element.preservesPitch = false;
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
