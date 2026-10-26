import {AudioEngine,stamp} from './audio.js';
import {createSetRecorder} from './dj-recorder.js';

const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const rollModules=new WeakMap();
const text={
 en:{title:'DJ room',note:'Two tracks. Your transition.',load:'Choose track',play:'Play',pause:'Pause',volume:'Level',speed:'Speed',pitch:'Tone',bass:'Bass',treble:'Highs',advanced:'Deck controls',cross:'Crossfader',center:'Center',cue:'Cue points',clear:'Clear cues',roll:'Roll',off:'Off',rollNote:'Repeats the last fragment. Turn it off to return to the running track.',bpm:'Tempo · BPM',tap:'Tap the beat',sync:'Match tempo',needBpm:'Set both BPM values or tap along to the beat.',loaded:'Track ready',choose:'Choose a track first',record:'Record set',stop:'Stop recording',ready:'Set ready. Save it before closing.',download:'Download MP3',save:'Save to My music',working:'Preparing your set…',saved:'Saved to My music',unsupported:'Recording is not supported in this browser',cueSaved:'Cue saved',empty:'No track yet',reset:'Reset deck',loading:'Loading…',recordHint:'Records the two decks and your transitions.',recording:'Recording',startBoth:'Start both',pauseBoth:'Pause both'},
 ru:{title:'DJ-комната',note:'Два трека. Твой переход.',load:'Выбрать трек',play:'Играть',pause:'Пауза',volume:'Громкость',speed:'Скорость',pitch:'Тон',bass:'Бас',treble:'Высокие',advanced:'Настройки деки',cross:'Переход между треками',center:'По центру',cue:'Точки возврата',clear:'Сбросить точки',roll:'Roll',off:'Выкл.',rollNote:'Повторяет последний фрагмент. Выключи — вернёшься к текущей позиции трека.',bpm:'Темп · BPM',tap:'Нажимай в ритм',sync:'Темп как у другой',needBpm:'Укажи BPM обоих треков или нажми Tap в ритм музыки.',loaded:'Трек готов',choose:'Сначала выбери трек',record:'Записать сет',stop:'Остановить запись',ready:'Сет готов',download:'Скачать MP3',save:'В Мою музыку',working:'Готовлю твой сет…',saved:'Сохранено в Моей музыке',unsupported:'Запись не поддерживается этим браузером',cueSaved:'Точка сохранена',empty:'Трек ещё не выбран',reset:'Сбросить деку',loading:'Загружаю…',recordHint:'Записывает звук обеих дек и твои переходы.',recording:'Идёт запись',startBoth:'Включить обе',pauseBoth:'Пауза на обеих'}
};

Object.assign(text.en,{position:'Track position'});
Object.assign(text.ru,{position:'Позиция трека',ready:'Сет готов. Сохрани перед закрытием.'});

export class DJRoom {
 constructor(options){
  Object.assign(this,options);this.cross=50;this.decks={};this.busy=false;this.recorded=null;this.exported=null;
  for(const key of ['A','B'])this.decks[key]={key,audio:new Audio(),track:null,speed:1,pitch:0,volume:.85,bass:0,treble:0,bpm:0,cues:[null,null,null],taps:[],roll:0,loading:false};
 }
 t(key){return (text[this.language()]||text.en)[key]||key;}
 async ensure(){
  if(this.initializing)return this.initializing;
  this.initializing=(async()=>{
   const context=await this.getContext();this.context=context;
   this.mix=context.createGain();this.mix.gain.value=.7;
   this.limiter=context.createDynamicsCompressor();this.limiter.threshold.value=-1;this.limiter.knee.value=0;this.limiter.ratio.value=20;this.limiter.attack.value=.002;this.limiter.release.value=.08;
   this.mix.connect(this.limiter);this.limiter.connect(context.destination);
   this.destination=context.createMediaStreamDestination();this.limiter.connect(this.destination);
   if(context.audioWorklet){
    if(!rollModules.has(context))rollModules.set(context,context.audioWorklet.addModule(new URL('./dj-loop-processor.js',import.meta.url).href));
    await rollModules.get(context);
   }
   for(const d of Object.values(this.decks)){
    d.gain=context.createGain();d.gain.connect(this.mix);
    d.meter=context.createAnalyser();d.meter.fftSize=256;d.samples=new Float32Array(256);d.gain.connect(d.meter);
    if(context.audioWorklet){
     d.loopNode=new AudioWorkletNode(context,'swidj-roll',{outputChannelCount:[2]});
     d.loopNode.port.onmessage=({data})=>{d.rollActive=!!data.active;if(data.active)d.captureSpeed=d.speed;this.syncRollRate(d);this.update();};
    }
    d.engine=new AudioEngine(d.audio,{context,destination:d.gain,inputNode:d.loopNode});
    d.audio.preload='metadata';d.audio.addEventListener('play',()=>{this.pauseMain();d.loopNode?.port.postMessage({type:'transport',playing:true,feeding:d.audio.readyState>=3});this.setCross(this.cross);this.update();});
    d.audio.addEventListener('playing',()=>d.loopNode?.port.postMessage({type:'feeding',feeding:true}));
    d.audio.addEventListener('waiting',()=>d.loopNode?.port.postMessage({type:'feeding',feeding:false}));
    d.audio.addEventListener('pause',()=>{d.loopNode?.port.postMessage({type:'transport',playing:false,feeding:false});this.setCross(this.cross);this.update();});d.audio.addEventListener('ended',()=>this.update());
    d.audio.addEventListener('error',()=>this.onError(new Error('invalidAudio')));
    await d.engine.unlock();
   }
   this.setCross(this.cross);
  })();
  try{return await this.initializing;}catch(error){this.initializing=null;throw error;}
 }
 deckMarkup(d){
  const range=(name,label,min,max,step,value)=>`<label>${this.t(label)}<output data-dj-output="${d.key}:${name}">${value}</output><input data-dj-control="${name}" data-deck="${d.key}" type="range" min="${min}" max="${max}" step="${step}" value="${value}"></label>`;
  return `<section class="dj-deck deck-${d.key.toLowerCase()}" data-dj-deck="${d.key}"><div class="dj-deck-head"><span class="dj-letter">${d.key}</span><button type="button" class="chip" data-dj-action="load" data-deck="${d.key}">${this.t(d.loading?'loading':'load')}</button></div><h2 data-dj-title="${d.key}">${escape(d.track?.title||this.t('empty'))}</h2><p class="dj-artist">${escape(d.track?.artist||'')}</p><div class="dj-timeline"><span data-dj-time="${d.key}">${stamp(d.audio.currentTime)}</span><input type="range" min="0" max="1000" value="0" data-dj-control="seek" data-deck="${d.key}" aria-label="${this.t('position')} ${d.key}"><span>${stamp(d.track?.duration||d.audio.duration)}</span></div><button type="button" class="btn dj-play" data-dj-action="play" data-deck="${d.key}" ${!d.track||d.loading?'disabled':''}>${this.t(d.audio.paused?'play':'pause')}</button><div class="dj-cues"><small>${this.t('cue')}</small>${d.cues.map((cue,i)=>`<button type="button" class="chip ${cue!==null?'active':''}" data-dj-action="cue" data-deck="${d.key}" data-cue="${i}">${i+1}${cue!==null?' · '+stamp(cue):''}</button>`).join('')}</div><div class="dj-roll"><small>${this.t('roll')}</small>${[2,4,8].map(seconds=>`<button type="button" class="chip ${d.roll===seconds?'active':''}" data-dj-action="roll" data-deck="${d.key}" data-seconds="${seconds}">${seconds}s</button>`).join('')}<button type="button" class="text-btn" data-dj-action="roll" data-deck="${d.key}" data-seconds="0">${this.t('off')}</button></div><details class="dj-controls"><summary>${this.t('advanced')}</summary>${range('volume','volume',0,1,.01,d.volume)}${range('speed','speed',.5,2,.01,d.speed)}${range('pitch','pitch',-12,12,.1,d.pitch)}${range('bass','bass',-6,9,1,d.bass)}${range('treble','treble',-6,6,1,d.treble)}<div class="dj-bpm"><label>${this.t('bpm')}<input type="number" min="30" max="300" step=".1" value="${d.bpm||''}" data-dj-control="bpm" data-deck="${d.key}"></label><button type="button" class="chip" data-dj-action="tap" data-deck="${d.key}">${this.t('tap')}</button><button type="button" class="chip" data-dj-action="sync" data-deck="${d.key}">${this.t('sync')}</button></div><p class="fineprint">${this.t('rollNote')}</p><button type="button" class="text-btn" data-dj-action="clear-cues" data-deck="${d.key}">${this.t('clear')}</button><button type="button" class="text-btn" data-dj-action="reset" data-deck="${d.key}">${this.t('reset')}</button></details></section>`;
 }
 mount(root){
  this.root=root;this.active=true;
  root.innerHTML=`<section class="dj-heading"><p class="eyebrow">SWIDJ / DJ</p><h1>${this.t('title')}</h1><p>${this.t('note')}</p></section><div class="dj-decks">${Object.values(this.decks).map(d=>this.deckMarkup(d)).join('')}</div><section class="dj-mixer"><label for="dj-cross">${this.t('cross')}</label><div class="dj-cross-labels"><strong>A</strong><button type="button" class="text-btn" data-dj-action="center">${this.t('center')}</button><strong>B</strong></div><input id="dj-cross" type="range" min="0" max="100" step="1" value="${this.cross}" data-dj-control="cross"><div class="dj-both"><button type="button" class="btn secondary" data-dj-action="start-all">${this.t('startBoth')}</button><button type="button" class="text-btn" data-dj-action="pause-all">${this.t('pauseBoth')}</button></div></section><section class="dj-record"><p class="fineprint">${this.t('recordHint')}</p><button type="button" class="btn" data-dj-action="record">${this.t('record')}</button><span id="dj-record-state" role="status"></span><div class="dj-export" hidden><button type="button" class="btn secondary" data-dj-action="download">${this.t('download')}</button><button type="button" class="btn secondary" data-dj-action="save">${this.t('save')}</button></div></section>`;
  root.onclick=event=>{const button=event.target.closest('[data-dj-action]');if(button)this.action(button).catch(this.onError);};
  for(const d of Object.values(this.decks)){
    const details=root.querySelector(`[data-dj-deck="${d.key}"] details`);details.open=!!d.expanded;details.addEventListener('toggle',()=>{d.expanded=details.open;});
    root.querySelector(`[data-dj-title="${d.key}"]`).insertAdjacentHTML('afterend',`<meter class="dj-meter" min="0" max="1" value="0" aria-label="${d.key} level"></meter>`);
  }
  root.oninput=event=>{if(event.target.dataset.djControl)this.control(event.target);};
  clearInterval(this.timer);this.timer=setInterval(()=>this.update(),200);this.update();
 }
 async load(key,track){
  const d=this.decks[key];if(!d||d.loading)return;
  const revision=(d.loadRevision||0)+1;d.loadRevision=revision;d.loading=true;d.audio.pause();this.update();
  try{
   await this.ensure();
   const source=await this.getSource(track,{cancelled:()=>revision!==d.loadRevision||!this.active});if(!source||revision!==d.loadRevision)return;
   d.loopNode?.port.postMessage({type:'reset'});d.loopNode?.port.postMessage({type:'transport',playing:false,feeding:false});d.engine.resetPitch();
   if(d.blobUrl)URL.revokeObjectURL(d.blobUrl);d.blobUrl=source.url.startsWith('blob:')?source.url:null;
   d.track=source.track;d.audio.src=source.url;d.cues=[null,null,null];d.roll=0;d.rollActive=false;d.bpm=0;d.taps=[];
   d.engine.inputPitchRatio=1;d.engine.setSpeed(d.speed);d.engine.setPitch(d.pitch);d.engine.setBass(d.bass);d.engine.setTreble(d.treble);
   this.notify(this.t('loaded'));this.remount();
  }finally{if(revision===d.loadRevision)d.loading=false;this.update();}
 }
 remount(){if(this.root?.isConnected)this.mount(this.root);}
 setCross(value){
  this.cross=Math.max(0,Math.min(100,Number(value)));
  const theta=this.cross/100*Math.PI/2;
  for(const d of Object.values(this.decks))if(d.gain){const gain=d.gain.gain,now=this.context.currentTime;if(gain.cancelAndHoldAtTime)gain.cancelAndHoldAtTime(now);else gain.cancelScheduledValues(now);gain.setTargetAtTime(d.audio.paused?0:d.volume*(d.key==='A'?Math.cos(theta):Math.sin(theta)),now,.015);}
 }
 syncRollRate(d){
  const ratio=d.rollActive?d.speed/(d.captureSpeed||d.speed):1;
  if(d.loopNode)d.loopNode.parameters.get('rate').value=ratio;
  if(d.engine){d.engine.inputPitchRatio=ratio;d.engine.syncPitch();}
 }
 control(node){
  const key=node.dataset.djControl,value=Number(node.value),d=this.decks[node.dataset.deck];
  if(key==='cross'){this.setCross(value);return;}
  if(!d||!Number.isFinite(value))return;
  if(key==='seek'){
   if(!Number.isFinite(d.audio.duration))return;
   d.loopNode?.port.postMessage({type:'reset'});d.roll=0;d.rollActive=false;this.syncRollRate(d);d.engine?.resetPitch();d.audio.currentTime=d.audio.duration*value/1000;return;
  }
  if(key==='bpm'){d.bpm=value>=30&&value<=300?value:0;return;}
  d[key]=value;
  const output=this.root?.querySelector(`[data-dj-output="${d.key}:${key}"]`);if(output)output.textContent=Number(value.toFixed(2));
  if(key==='volume')this.setCross(this.cross);
  if(key==='speed'){d.engine?.setSpeed(value);this.syncRollRate(d);}
  if(key==='pitch')d.engine?.setPitch(value);
  if(key==='bass')d.engine?.setBass(value);
  if(key==='treble')d.engine?.setTreble(value);
 }
 async play(d){if(!d.track)return this.notify(this.t('choose'));await this.ensure();await d.engine.unlock();this.pauseMain();await d.audio.play();}
 async action(button){
  const action=button.dataset.djAction,d=this.decks[button.dataset.deck];
  if(action==='load')return this.choose(d.key);
  if(action==='center'){this.setCross(50);this.root.querySelector('#dj-cross').value=50;return;}
  if(action==='pause-all'){for(const deck of Object.values(this.decks))deck.audio.pause();return;}
  if(action==='start-all'){await this.ensure();await Promise.all(Object.values(this.decks).filter(deck=>deck.track).map(deck=>this.play(deck)));return;}
  if(action==='record')return this.toggleRecording();
  if(action==='download'||action==='save')return this.deliver(action);
  if(!d)return;
  if(action==='play'){if(d.audio.paused)await this.play(d);else d.audio.pause();return;}
  if(!d.track)return this.notify(this.t('choose'));
  if(action==='cue'){
   const index=Number(button.dataset.cue);
   if(d.cues[index]===null){d.cues[index]=d.audio.currentTime;this.notify(this.t('cueSaved'));}
   else {d.loopNode?.port.postMessage({type:'reset'});d.roll=0;d.rollActive=false;this.syncRollRate(d);d.engine.resetPitch();d.audio.currentTime=d.cues[index];}
   this.update();return;
  }
  if(action==='clear-cues'){d.cues=[null,null,null];this.update();return;}
  if(action==='roll'){
   if(!d.loopNode)return this.notify(this.t('unsupported'));
   d.roll=d.roll===Number(button.dataset.seconds)?0:Number(button.dataset.seconds);d.loopNode.port.postMessage({type:'roll',seconds:d.roll});this.update();return;
  }
  if(action==='tap'){
   const now=performance.now();if(now-(d.taps.at(-1)||0)>2000)d.taps=[];
   d.taps.push(now);d.taps=d.taps.slice(-6);
   if(d.taps.length>1){const bpm=60000*(d.taps.length-1)/(d.taps.at(-1)-d.taps[0]);if(bpm>=30&&bpm<=300)d.bpm=Math.round(bpm*10)/10;}
   this.update();return;
  }
  if(action==='sync'){
   const other=this.decks[d.key==='A'?'B':'A'];if(!d.bpm||!other.bpm)return this.notify(this.t('needBpm'));
   const speed=other.bpm*other.speed/d.bpm;
   if(speed<.5||speed>2)return this.notify(this.language()==='ru'?'Темпы слишком разные для такого перехода. Попробуй другой трек.':'These tempos are too far apart for this transition. Try another track.');
   d.speed=speed;d.engine.setSpeed(d.speed);this.syncRollRate(d);this.remount();return;
  }
  if(action==='reset'){d.speed=1;d.pitch=0;d.bass=0;d.treble=0;d.volume=.85;d.engine.setPitch(0);d.engine.setSpeed(1);d.engine.setBass(0);d.engine.setTreble(0);this.syncRollRate(d);this.setCross(this.cross);this.remount();}
 }
 async toggleRecording(){
  if(this.recordFinishing)return;
  if(this.recorder?.state==='recording'){this.recordFinishing=true;this.recorder.stop();return;}
  if(this.busy)return;
  if(!Object.values(this.decks).some(d=>d.track))return this.notify(this.t('choose'));
  await this.ensure();
  try{this.recorder=await createSetRecorder(this.context,this.limiter,this.destination.stream);}catch{return this.notify(this.t('unsupported'));}
  const mime=this.recorder.mimeType;
  const chunks=[];let bytes=0;this.recorded=null;this.exported=null;this.recordStarted=Date.now();this.recordFailure=false;
  this.recordTitle='SwiDJ DJ · '+new Date().toLocaleString(this.language()==='ru'?'ru-RU':'en-GB',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});
  this.recorder.onerror=()=>{this.recordFailure=true;this.recordFinishing=false;this.notify(this.t('unsupported'));this.update();};
  this.recorder.ondataavailable=event=>{chunks.push(event.data);bytes+=event.data.size;if(bytes>250*1024**2&&this.recorder.state==='recording')this.recorder.stop();};
  this.recorder.onstop=()=>{clearTimeout(this.recordLimit);this.recordFinishing=false;this.recorded=!this.recordFailure&&bytes>44?new Blob(chunks,{type:mime}):null;if(!this.recorded)this.notify(this.t('unsupported'));this.update();};
  this.recorder.start(1000);this.recordLimit=setTimeout(()=>{if(this.recorder?.state==='recording')this.recorder.stop();},Math.min(7198,this.recorder.maxDuration||7198)*1000);this.update();
 }
 async deliver(action){
  if(this.busy||!this.recorded)return;this.busy=true;this.update();
  try{
   if(!this.exported){
    const form=new FormData();form.append('settings',JSON.stringify({background:true,format:'mp3',delivery:'ticket',title:this.recordTitle||'SwiDJ DJ set'}));form.append('file',this.recorded,'DJ-set.audio');
    let info=await(await this.request('studio',form)).json();
    if(info.job){const job=info.job;while(['queued','processing'].includes(info.status)){await new Promise(r=>setTimeout(r,900));info=await(await this.request('studio/jobs/'+job)).json();}if(info.status!=='ready')throw new Error(info.error||'error');info=info.file;}
    this.exported=info;
   }
   if(action==='download')this.download(this.exported);
   else {const result=await(await this.request('studio/save',{ticket:new URL(this.exported.url).pathname.split('/').pop()})).json();this.saved(result);this.notify(this.t('saved'));}
  }finally{this.busy=false;this.update();}
 }
 update(){
  if(!this.root?.isConnected)return;
  for(const d of Object.values(this.decks)){
   const deck=this.root.querySelector(`[data-dj-deck="${d.key}"]`);if(!deck)continue;
   deck.classList.toggle('playing',!d.audio.paused);
   if(d.meter){d.meter.getFloatTimeDomainData(d.samples);deck.querySelector('meter').value=Math.min(1,Math.sqrt(d.samples.reduce((sum,n)=>sum+n*n,0)/d.samples.length)*3);}
   const play=deck.querySelector('[data-dj-action="play"]');play.textContent=this.t(d.audio.paused?'play':'pause');play.disabled=!d.track||d.loading;
   deck.querySelector('[data-dj-action="load"]').disabled=d.loading;deck.querySelector('[data-dj-action="load"]').textContent=this.t(d.loading?'loading':'load');
   deck.querySelector('[data-dj-time]').textContent=stamp(d.audio.currentTime);
   const seek=deck.querySelector('[data-dj-control="seek"]');if(document.activeElement!==seek)seek.value=Number.isFinite(d.audio.duration)?d.audio.currentTime/d.audio.duration*1000:0;
   for(const button of deck.querySelectorAll('[data-dj-action="cue"]')){const i=Number(button.dataset.cue);button.textContent=String(i+1)+(d.cues[i]!==null?' · '+stamp(d.cues[i]):'');button.classList.toggle('active',d.cues[i]!==null);}
   for(const button of deck.querySelectorAll('[data-dj-action="roll"]'))button.classList.toggle('active',d.roll===Number(button.dataset.seconds)&&d.roll!==0);
   const bpm=deck.querySelector('[data-dj-control="bpm"]');if(document.activeElement!==bpm)bpm.value=d.bpm||'';
  }
  const recording=this.recorder?.state==='recording';
  const button=this.root.querySelector('[data-dj-action="record"]');button.textContent=this.t(recording?'stop':'record');button.classList.toggle('recording',recording);button.disabled=this.busy;
  this.root.querySelector('#dj-record-state').textContent=this.busy?this.t('working'):recording?this.t('recording')+' · '+stamp((Date.now()-this.recordStarted)/1000):this.recorded?this.t('ready'):'';
  this.root.querySelector('.dj-export').hidden=!this.recorded||recording;
  for(const action of this.root.querySelectorAll('.dj-export button'))action.disabled=this.busy;
 }
 pauseAll(){this.active=false;for(const d of Object.values(this.decks)){d.loadRevision=(d.loadRevision||0)+1;d.loading=false;d.audio.pause();}if(this.recorder?.state==='recording'){this.recordFinishing=true;this.recorder.stop();}clearInterval(this.timer);}
}
