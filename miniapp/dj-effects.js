// Per-deck transitions. All controls ramp on the audio clock, never replace media.
export class DJEffects {
 constructor(context,destination){
  this.context=context;this.input=context.createGain();
  this.low=context.createBiquadFilter();this.low.type='lowpass';this.low.frequency.value=22000;this.low.Q.value=.5;
  this.high=context.createBiquadFilter();this.high.type='highpass';this.high.frequency.value=20;this.high.Q.value=.5;
  this.bass=context.createBiquadFilter();this.bass.type='lowshelf';this.bass.frequency.value=180;
  this.dry=context.createGain();this.send=context.createGain();this.send.gain.value=0;
  this.delay=context.createDelay(2);this.delay.delayTime.value=.375;
  this.feedback=context.createGain();this.feedback.gain.value=.42;
  this.damping=context.createBiquadFilter();this.damping.type='lowpass';this.damping.frequency.value=4200;
  this.wet=context.createGain();this.wet.gain.value=.6;
  this.input.connect(this.low).connect(this.high).connect(this.bass);
  this.bass.connect(this.dry).connect(destination);this.bass.connect(this.send).connect(this.delay);
  this.delay.connect(this.damping).connect(this.feedback).connect(this.delay);this.damping.connect(this.wet).connect(destination);
 }
 ramp(param,value,time=.025){const at=this.context.currentTime;if(param.cancelAndHoldAtTime)param.cancelAndHoldAtTime(at);else param.cancelScheduledValues(at);param.setTargetAtTime(value,at,time);}
 set(filter=0,bassCut=0){
  this.ramp(this.low.frequency,filter<0?22000*Math.pow(180/22000,-filter):22000);
  this.ramp(this.high.frequency,filter>0?20*Math.pow(4500/20,filter):20);
  this.ramp(this.bass.gain,-30*bassCut);
 }
 echoOut(bpm=120){
  clearTimeout(this.echoTimer);this.out=true;
  this.ramp(this.delay.delayTime,Math.max(.12,Math.min(1.5,60/bpm*.75)),.04);
  this.ramp(this.send.gain,.8,.02);this.ramp(this.dry.gain,0,.06);
  this.echoTimer=setTimeout(()=>this.ramp(this.send.gain,0,.05),Math.min(1800,240000/bpm));
 }
 restore(){clearTimeout(this.echoTimer);this.out=false;this.ramp(this.dry.gain,1);this.ramp(this.send.gain,0);}
}
