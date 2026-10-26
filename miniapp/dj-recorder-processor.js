class SwiDJRecorder extends AudioWorkletProcessor {
 constructor(){super();this.recording=false;this.buffer=new Int16Array(16384);this.used=0;this.port.onmessage=({data})=>{if(data==='start')this.recording=true;if(data==='stop'){this.recording=false;this.flush();this.done=true;this.port.postMessage({type:'done'});}};}
 flush(){if(!this.used)return;const chunk=this.buffer.slice(0,this.used);this.port.postMessage({type:'chunk',buffer:chunk.buffer},[chunk.buffer]);this.used=0;}
 process(inputs,outputs){
  if(this.done)return false;
  for(const channel of outputs[0]||[])channel.fill(0);
  const input=inputs[0];if(!this.recording||!input?.length)return true;
  for(let i=0;i<input[0].length;i++)for(let c=0;c<2;c++){
   const value=Math.max(-1,Math.min(1,input[c]?.[i]??input[0][i]));this.buffer[this.used++]=Math.round(value*(value<0?32768:32767));
   if(this.used===this.buffer.length)this.flush();
  }
  return true;
 }
}
registerProcessor('swidj-recorder',SwiDJRecorder);
