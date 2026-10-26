const registered=new WeakMap();

class PCMRecorder {
 constructor(context,input){this.context=context;this.input=input;this.state='inactive';this.mimeType='audio/wav';this.maxDuration=Math.floor((250*1024**2-44)/(context.sampleRate*4))-2;}
 async prepare(){
  if(!registered.has(this.context))registered.set(this.context,this.context.audioWorklet.addModule(new URL('./dj-recorder-processor.js',import.meta.url).href));
  await registered.get(this.context);
  this.node=new AudioWorkletNode(this.context,'swidj-recorder',{outputChannelCount:[2]});this.silent=this.context.createGain();this.silent.gain.value=0;
  this.input.connect(this.node);this.node.connect(this.silent).connect(this.context.destination);
  this.node.port.onmessage=({data})=>{
   if(data.type==='chunk'){this.chunks.push(data.buffer);this.bytes+=data.buffer.byteLength;if(this.bytes>=250*1024**2&&this.state==='recording')this.stop();}
   if(data.type==='done'){
    const header=new ArrayBuffer(44),view=new DataView(header),write=(at,value)=>[...value].forEach((c,i)=>view.setUint8(at+i,c.charCodeAt(0)));
    write(0,'RIFF');view.setUint32(4,36+this.bytes,true);write(8,'WAVE');write(12,'fmt ');view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,2,true);view.setUint32(24,this.context.sampleRate,true);view.setUint32(28,this.context.sampleRate*4,true);view.setUint16(32,4,true);view.setUint16(34,16,true);write(36,'data');view.setUint32(40,this.bytes,true);
    const blob=new Blob([header,...this.chunks],{type:'audio/wav'});this.chunks=[];
    this.input.disconnect(this.node);this.node.disconnect();this.silent.disconnect();this.node.port.close();this.ondataavailable?.({data:blob});this.onstop?.();
   }
  };
  return this;
 }
 start(){this.chunks=[];this.bytes=0;this.state='recording';this.node.port.postMessage('start');}
 stop(){if(this.state!=='recording')return;this.state='inactive';this.node.port.postMessage('stop');}
}

export async function createSetRecorder(context,input,stream){
 for(const mimeType of ['audio/webm;codecs=opus','audio/mp4','audio/webm']){
  if(globalThis.MediaRecorder?.isTypeSupported(mimeType)){
   try{return new MediaRecorder(stream,{mimeType,audioBitsPerSecond:192000});}catch{}
  }
 }
 if(context.audioWorklet)return new PCMRecorder(context,input).prepare();
 throw new Error('unavailable');
}
