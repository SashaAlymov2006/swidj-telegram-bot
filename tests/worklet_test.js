// Executes actual DSP code with an AudioWorklet port shim; not physical-device QA.
const processors=new Map();
globalThis.sampleRate=48000;
globalThis.AudioWorkletProcessor=class{constructor(){this.messages=[];this.port={postMessage:value=>this.messages.push(value)};}};
globalThis.registerProcessor=(name,value)=>processors.set(name,value);
await import('../miniapp/dj-loop-processor.js');
await import('../miniapp/dj-recorder-processor.js');
await import('../miniapp/soundtouch-processor.js');
const assert=value=>{if(!value)throw Error('Audio DSP assertion failed');};
const signal=(block)=>Float32Array.from({length:128},(_,i)=>.3*Math.sin((block*128+i)*Math.PI*2*440/sampleRate));
const output=()=>[new Float32Array(128),new Float32Array(128)];
const valid=channels=>{for(const channel of channels)for(const value of channel)assert(Number.isFinite(value)&&Math.abs(value)<1.1);};
Deno.test('DJ roll and beat loop capture live audio, play at varying rates and stop cleanly',()=>{
 const processor=new (processors.get('swidj-roll'))();
 const send=data=>processor.port.onmessage({data});send({type:'transport',playing:true,feeding:true});send({type:'roll',seconds:2});
 for(let i=0;i<800;i++){const out=output();processor.process([[signal(i)]],[out],{rate:[1]});valid(out);}
 assert(processor.messages.some(v=>v.active));let energy=0;
 send({type:'feeding',feeding:false});
 for(const rate of [.5,1,1.5,2]){const out=output();processor.process([[]],[out],{rate:[rate]});valid(out);energy+=out[0].reduce((a,v)=>a+v*v,0);}
 assert(energy>0);send({type:'loop',seconds:.25});send({type:'feeding',feeding:true});
 for(let i=0;i<150;i++){const out=output();processor.process([[signal(i)]],[out],{rate:[1]});valid(out);}
 assert(processor.messages.some(v=>v.loop));send({type:'transport',playing:false,feeding:false});
 const stopped=output();processor.process([[]],[stopped],{rate:[1]});processor.process([[]],[stopped],{rate:[1]});assert(stopped[0].every(v=>v===0));
});
Deno.test('DJ recorder captures stereo, bounds samples and flushes the final chunk',()=>{
 const processor=new (processors.get('swidj-recorder'))();processor.port.onmessage({data:'start'});
 const out=output();processor.process([[Float32Array.of(-2,2,.5),Float32Array.of(2,-2,-.5)]],[out]);processor.port.onmessage({data:'stop'});
 const pcm=new Int16Array(processor.messages.find(v=>v.type==='chunk').buffer);
 assert(pcm.length===6&&pcm[0]===-32768&&pcm[1]===32767&&pcm[2]===32767&&pcm[3]===-32768);
 assert(processor.messages.at(-1).type==='done'&&processor.process([],[])===false);
});
Deno.test('Tone and speed work together through live changes and an explicit seek reset',()=>{
 const processor=new (processors.get('soundtouch-processor'))();let energy=0;
 for(let block=0;block<1800;block++){
  if(block===900)processor.port.onmessage({data:{type:'swidj-reset'}});
  const out=output(),pitch=block<600?-5:block<1200?4:0,rate=block<900?.8:1.2;
  assert(processor.process([[signal(block)]],[out],{pitch:[1],pitchSemitones:[pitch],playbackRate:[rate]}));valid(out);
  energy+=out[0].reduce((sum,v)=>sum+v*v,0);
 }
 assert(energy>100);
});
