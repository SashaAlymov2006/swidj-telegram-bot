// A small per-deck slip-roll buffer. No network, microphone, or full-track decoding.
class SwiDJRoll extends AudioWorkletProcessor {
  static get parameterDescriptors(){return [{name:'rate',defaultValue:1,minValue:.25,maxValue:4,automationRate:'k-rate'}];}
  constructor(){
    super();this.capacity=Math.ceil(sampleRate*8);this.buffers=[new Float32Array(this.capacity),new Float32Array(this.capacity)];
    this.write=0;this.captured=0;this.frames=0;this.wanted=0;this.cursor=0;this.fade=0;this.last=[0,0];this.playing=false;this.feeding=false;
    this.port.onmessage=({data})=>{
      if(data.type==='reset'){this.write=0;this.captured=0;this.frames=0;this.wanted=0;this.fade=128;}
      if(data.type==='transport'){this.playing=!!data.playing;this.feeding=!!data.feeding;this.fade=128;this.stopSample=[...this.last];}
      if(data.type==='feeding')this.feeding=!!data.feeding;
      if(data.type==='roll'){
        this.wanted=[2,4,8].includes(data.seconds)?Math.floor(data.seconds*sampleRate):0;
        if(this.wanted)this.frames=0;
        if(!this.wanted){this.frames=0;this.fade=128;this.port.postMessage({active:false});}
      }
    };
  }
  process(inputs,outputs,parameters){
    const input=inputs[0],output=outputs[0];if(!output?.length)return true;
    const step=parameters.rate[0];
    for(let i=0;i<output[0].length;i++){
      if(!this.playing){for(let c=0;c<output.length;c++){output[c][i]=(this.stopSample?.[Math.min(c,1)]||0)*this.fade/128;this.last[Math.min(c,1)]=output[c][i];}if(this.fade>0)this.fade--;continue;}
      if(!this.frames&&this.feeding){
        for(let c=0;c<2;c++)this.buffers[c][this.write]=input?.[c]?.[i]??input?.[0]?.[i]??0;
        this.write=(this.write+1)%this.capacity;this.captured=Math.min(this.capacity,this.captured+1);
        if(this.wanted&&this.captured>=this.wanted){
          this.frames=this.wanted;this.start=(this.write-this.frames+this.capacity)%this.capacity;this.cursor=0;this.fade=128;
          this.port.postMessage({active:true,seconds:this.frames/sampleRate});
        }
      }
      for(let c=0;c<output.length;c++){
        let value;
        if(this.frames){
          const buffer=this.buffers[Math.min(c,1)],base=Math.floor(this.cursor),fraction=this.cursor-base;
          const at=n=>buffer[(this.start+(n%this.frames))%this.capacity];
          value=at(base)*(1-fraction)+at(base+1)*fraction;
          if(this.cursor>this.frames-128){const mix=(this.cursor-(this.frames-128))/128;value=value*(1-mix)+at(Math.floor(this.cursor-(this.frames-128)))*mix;}
        }else value=this.feeding?(input?.[c]?.[i]??input?.[0]?.[i]??0):0;
        if(this.fade>0)value=this.last[Math.min(c,1)]*(this.fade/128)+value*(1-this.fade/128);
        output[c][i]=Number.isFinite(value)?value:0;
        this.last[Math.min(c,1)]=output[c][i];
      }
      if(this.fade>0)this.fade--;
      if(this.frames){this.cursor+=step;if(this.cursor>=this.frames)this.cursor=128+(this.cursor-this.frames);}
    }
    return true;
  }
}
registerProcessor('swidj-roll',SwiDJRoll);
