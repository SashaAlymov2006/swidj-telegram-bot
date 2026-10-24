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

export function chain(context, source, destination, bass) {
  const headroom = context.createGain();
  headroom.gain.value = 10 ** (-Math.max(0, bass) / 20);
  const filter = context.createBiquadFilter(); filter.type = 'lowshelf'; filter.frequency.value = 100; filter.gain.value = bass;
  const compressor = context.createDynamicsCompressor();
  compressor.threshold.value = -2; compressor.knee.value = 0; compressor.ratio.value = 20;
  compressor.attack.value = .002; compressor.release.value = .1;
  source.connect(headroom).connect(filter).connect(compressor).connect(destination);
  return {headroom, filter};
}

export class AudioEngine {
  constructor(element) { this.element = element; this.bass = 0; this.speed = 1; }
  async unlock() {
    if (!this.context) {
      this.context = new AudioContext();
      this.nodes = chain(this.context, this.context.createMediaElementSource(this.element), this.context.destination, this.bass);
    }
    await this.context.resume();
  }
  setBass(value) {
    this.bass = value;
    if (this.nodes) {
      this.nodes.headroom.gain.setTargetAtTime(10 ** (-Math.max(0, value) / 20), this.context.currentTime, .03);
      this.nodes.filter.gain.setTargetAtTime(value, this.context.currentTime, .03);
    }
  }
  setSpeed(value) {
    this.speed = value; this.element.playbackRate = value;
    // Match offline export: changing speed also changes pitch.
    this.element.preservesPitch = false;
  }
  async render(blob, preview = false) {
    await this.unlock();
    const input = await this.context.decodeAudioData(await blob.arrayBuffer());
    // Bound mobile memory. Long/full MP3 processing remains available in the bot.
    if (input.duration > 180 && !preview) throw new Error('long');
    const duration = Math.min(input.duration / this.speed, preview ? 15 : 180);
    const rate = 44100;
    const offline = new OfflineAudioContext(Math.min(input.numberOfChannels, 2), Math.ceil(duration * rate), rate);
    const source = offline.createBufferSource(); source.buffer = input; source.playbackRate.value = this.speed;
    chain(offline, source, offline.destination, this.bass); source.start();
    return wavBlob(await offline.startRendering());
  }
}
