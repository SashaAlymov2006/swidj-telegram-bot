import {AudioEngine,stamp} from './audio.js';
import {createSetRecorder} from './dj-recorder.js';
import {DJEffects} from './dj-effects.js';

const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const rollModules=new WeakMap();
const text={
 en:{title:'DJ room',note:'Two tracks. Your transition.',load:'Choose track',play:'Play',pause:'Pause',volume:'Level',speed:'Speed',pitch:'Tone',bass:'Bass',treble:'Highs',advanced:'Deck controls',cross:'Crossfader',center:'Center',cue:'Cue points',clear:'Clear cues',roll:'Roll',off:'Off',rollNote:'Repeats the last fragment. Turn it off to return to the running track.',bpm:'Tempo · BPM',tap:'Tap the beat',sync:'Match tempo',needBpm:'Set both BPM values or tap along to the beat.',loaded:'Track ready',choose:'Choose a track first',record:'Record set',stop:'Stop recording',ready:'Set ready. Save it before closing.',download:'Download MP3',save:'Save to My music',working:'Preparing your set…',saved:'Saved to My music',unsupported:'Recording is not supported in this browser',cueSaved:'Cue saved',empty:'No track yet',reset:'Reset deck',loading:'Loading…',recordHint:'Records the two decks and your transitions.',recording:'Recording',startBoth:'Start both',pauseBoth:'Pause both'},
 ru:{title:'DJ-комната',note:'Два трека. Твой переход.',load:'Выбрать трек',play:'Играть',pause:'Пауза',volume:'Громкость',speed:'Скорость',pitch:'Тон',bass:'Бас',treble:'Высокие',advanced:'Настройки деки',cross:'Переход между треками',center:'По центру',cue:'Точки возврата',clear:'Сбросить точки',roll:'Roll',off:'Выкл.',rollNote:'Повторяет последний фрагмент. Выключи — вернёшься к текущей позиции трека.',bpm:'Темп · BPM',tap:'Нажимай в ритм',sync:'Темп как у другой',needBpm:'Укажи BPM обоих треков или нажми Tap в ритм музыки.',loaded:'Трек готов',choose:'Сначала выбери трек',record:'Записать сет',stop:'Остановить запись',ready:'Сет готов',download:'Скачать MP3',save:'В Мою музыку',working:'Готовлю твой сет…',saved:'Сохранено в Моей музыке',unsupported:'Запись не поддерживается этим браузером',cueSaved:'Точка сохранена',empty:'Трек ещё не выбран',reset:'Сбросить деку',loading:'Загружаю…',recordHint:'Записывает звук обеих дек и твои переходы.',recording:'Идёт запись',startBoth:'Включить обе',pauseBoth:'Пауза на обеих'}
};

Object.assign(text.en,{position:'Track position'});
Object.assign(text.ru,{position:'Позиция трека',ready:'Сет готов. Сохрани перед закрытием.'});
Object.assign(text.en,{analyse:'Analyze rhythm',analysing:'Analyzing rhythm…',analysisRetry:'Rhythm analysis unavailable. Tap to retry.',uncertain:'Set BPM or tap the beat',estimated:'Estimated BPM',wave:'Waveform · tap to seek',loop:'Loop · bars',loopPending:'Capturing loop',loopPlaying:'Loop playing',align:'Align beats',firstBeat:'Set beat here',half:'½ BPM',double:'×2 BPM',filter:'Filter',bassCut:'Bass cut',echo:'Echo Out',restore:'Return sound',project:'Set projects',projectSave:'Save project',projectNew:'Save as new',projectName:'Project name',projectSaved:'Project saved',projectOpen:'Open',projectDelete:'Delete',projectEmpty:'Your saved sets will appear here.',projectHint:'Tracks, cues and settings. Recording is saved separately.',projectLocal:'Save local tracks to My music before saving a project.',projectLoaded:'Project opened · press Play when ready',confirmLoad:'Open this project? Current deck settings will be replaced.',confirmDelete:'Delete this project?',cancel:'Cancel',confirm:'Continue',loopLong:'This loop is too long at this tempo. Choose fewer bars.',beatHint:'Adjust BPM and set the first beat if the grid needs correction.',resetFX:'Reset effects'});
Object.assign(text.ru,{analyse:'Определить ритм',analysing:'Определяю ритм…',analysisRetry:'Не удалось определить ритм. Нажми для повтора.',uncertain:'Укажи BPM или нажимай в ритм',estimated:'Оценка BPM',wave:'Волна · нажми для перемотки',loop:'Петля · такты',loopPending:'Записываю петлю',loopPlaying:'Петля звучит',align:'Совместить удары',firstBeat:'Удар в этой точке',half:'½ BPM',double:'×2 BPM',filter:'Фильтр',bassCut:'Убрать бас',echo:'Уход эхом',restore:'Вернуть звук',project:'Проекты сетов',projectSave:'Сохранить проект',projectNew:'Сохранить как новый',projectName:'Название проекта',projectSaved:'Проект сохранён',projectOpen:'Открыть',projectDelete:'Удалить',projectEmpty:'Здесь будут твои сохранённые сеты.',projectHint:'Треки, точки и настройки. Запись сохраняется отдельно.',projectLocal:'Сначала сохрани локальные треки в Мою музыку.',projectLoaded:'Проект открыт · нажми Играть, когда будешь готов',confirmLoad:'Открыть проект? Текущие настройки дек будут заменены.',confirmDelete:'Удалить этот проект?',cancel:'Отмена',confirm:'Продолжить',loopLong:'Для этого темпа петля слишком длинная. Выбери меньше тактов.',beatHint:'Если сетка не совпала, поправь BPM и отметь первый удар.',resetFX:'Сбросить эффекты'});

export class DJRoom {
 constructor(options){
  Object.assign(this,options);this.cross=50;this.decks={};this.busy=false;this.recorded=null;this.exported=null;
  this.focusDeck='A';this.projects=null;this.projectId='';this.projectName='';this.projectBusy=false;
  for(const key of ['A','B'])this.decks[key]={key,audio:new Audio(),track:null,speed:1,pitch:0,volume:.85,bass:0,treble:0,bpm:0,offset:0,filter:0,bassCut:0,cues:[null,null,null],taps:[],roll:0,loopBars:0,loading:false};
 }
 t(key){return (text[this.language()]||text.en)[key]||key;}
 formatControl(key,value){
  if(key==='volume'||key==='bassCut')return Math.round(value*100)+'%';
  if(key==='filter')return (value>0?'+':'')+Math.round(value*100)+'%';
  if(key==='speed')return value.toFixed(2)+'×';
  return (value>0?'+':'')+Number(value.toFixed(1))+(key==='pitch'?' st':' dB');
 }
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
    d.fx=new DJEffects(context,d.gain);d.fx.set(d.filter,d.bassCut);
    d.meter=context.createAnalyser();d.meter.fftSize=256;d.samples=new Float32Array(256);d.gain.connect(d.meter);
    if(context.audioWorklet){
     d.loopNode=new AudioWorkletNode(context,'swidj-roll',{outputChannelCount:[2]});
     d.loopNode.port.onmessage=({data})=>{d.rollActive=!!data.active;if(data.active&&!data.loop)d.captureSpeed=d.speed;if(data.active&&data.loop){d.loopTick=this.context.currentTime;d.loopElapsed=0;}this.syncRollRate(d);this.update();};
    }
    d.engine=new AudioEngine(d.audio,{context,destination:d.fx.input,inputNode:d.loopNode});
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
  const range=(name,label,min,max,step,value)=>`<label>${this.t(label)}<output data-dj-output="${d.key}:${name}">${this.formatControl(name,value)}</output><input data-dj-control="${name}" data-deck="${d.key}" type="range" min="${min}" max="${max}" step="${step}" value="${value}"></label>`;
  return `<section class="dj-deck deck-${d.key.toLowerCase()}" data-dj-deck="${d.key}"><div class="dj-deck-head"><span class="dj-letter">${d.key}</span><button type="button" class="chip" data-dj-action="load" data-deck="${d.key}">${this.t(d.loading?'loading':'load')}</button></div><h2 data-dj-title="${d.key}">${escape(d.track?.title||this.t('empty'))}</h2><p class="dj-artist">${escape(d.track?.artist||'')}</p><button type="button" class="btn dj-play" data-dj-action="play" data-deck="${d.key}" ${!d.track||d.loading?'disabled':''}>${this.t(d.audio.paused?'play':'pause')}</button>${this.waveMarkup(d)}<div class="dj-timeline"><span data-dj-time="${d.key}">${stamp(d.audio.currentTime)}</span><input type="range" min="0" max="1000" value="0" data-dj-control="seek" data-deck="${d.key}" aria-label="${this.t('position')} ${d.key}"><span>${stamp(d.track?.duration||d.audio.duration)}</span></div><div class="dj-cues"><small>${this.t('cue')}</small>${d.cues.map((cue,i)=>`<button type="button" class="chip ${cue!==null?'active':''}" data-dj-action="cue" data-deck="${d.key}" data-cue="${i}">${i+1}${cue!==null?' · '+stamp(cue):''}</button>`).join('')}</div><div class="dj-beat-controls"><strong data-dj-bpm="${d.key}">${d.bpm?Math.round(d.bpm*d.speed*10)/10+' BPM':'\u2014 BPM'}</strong><button type="button" class="chip" data-dj-action="sync" data-deck="${d.key}">${this.t('sync')}</button><button type="button" class="chip" data-dj-action="align" data-deck="${d.key}">${this.t('align')}</button></div><div class="dj-bar-loop"><small>${this.t('loop')}</small>${[1,2,4,8].map(bars=>`<button type="button" class="chip" data-dj-action="loop" data-deck="${d.key}" data-bars="${bars}">${bars}</button>`).join('')}<button type="button" class="text-btn" data-dj-action="loop" data-deck="${d.key}" data-bars="0">${this.t('off')}</button><span data-loop-status="${d.key}"></span></div><div class="dj-transition">${range('filter','filter',-1,1,.01,d.filter)}${range('bassCut','bassCut',0,1,.01,d.bassCut)}<button type="button" class="chip" data-dj-action="echo" data-deck="${d.key}">${this.t(d.fx?.out?'restore':'echo')}</button><button type="button" class="text-btn" data-dj-action="reset-fx" data-deck="${d.key}">${this.t('resetFX')}</button></div><div class="dj-roll"><small>${this.t('roll')}</small>${[2,4,8].map(seconds=>`<button type="button" class="chip ${d.roll===seconds?'active':''}" data-dj-action="roll" data-deck="${d.key}" data-seconds="${seconds}">${seconds}s</button>`).join('')}<button type="button" class="text-btn" data-dj-action="roll" data-deck="${d.key}" data-seconds="0">${this.t('off')}</button></div><details class="dj-controls"><summary>${this.t('advanced')}</summary>${range('volume','volume',0,1,.01,d.volume)}${range('speed','speed',.5,2,.01,d.speed)}${range('pitch','pitch',-12,12,.1,d.pitch)}${range('bass','bass',-6,9,1,d.bass)}${range('treble','treble',-6,6,1,d.treble)}<div class="dj-bpm"><label>${this.t('bpm')}<input type="number" min="30" max="300" step=".1" value="${d.bpm||''}" data-dj-control="bpm" data-deck="${d.key}"></label><button type="button" class="chip" data-dj-action="tap" data-deck="${d.key}">${this.t('tap')}</button><button type="button" class="chip" data-dj-action="half" data-deck="${d.key}">${this.t('half')}</button><button type="button" class="chip" data-dj-action="double" data-deck="${d.key}">${this.t('double')}</button><button type="button" class="chip" data-dj-action="first-beat" data-deck="${d.key}">${this.t('firstBeat')}</button><button type="button" class="text-btn" data-dj-action="analyse" data-deck="${d.key}">${this.t('analyse')}</button><p class="fineprint">${this.t('beatHint')}</p></div><p class="fineprint">${this.t('rollNote')}</p><button type="button" class="text-btn" data-dj-action="clear-cues" data-deck="${d.key}">${this.t('clear')}</button><button type="button" class="text-btn" data-dj-action="reset" data-deck="${d.key}">${this.t('reset')}</button></details></section>`;
 }
 mount(root){
  this.root=root;this.active=true;
  root.dataset.focus=this.focusDeck;
  root.innerHTML=`<section class="dj-heading"><p class="eyebrow">SWIDJ / DJ</p><h1>${this.t('title')}</h1><p>${this.t('note')}</p></section>${this.projectMarkup()}<div class="dj-deck-tabs">${['A','B'].map(key=>`<button type="button" data-dj-action="focus" data-deck="${key}" aria-pressed="${key===this.focusDeck}"><b>${key}</b><span>${escape(this.decks[key].track?.title||this.t('empty'))}</span></button>`).join('')}</div><div class="dj-decks">${Object.values(this.decks).map(d=>this.deckMarkup(d)).join('')}</div><section class="dj-mixer"><label for="dj-cross">${this.t('cross')}</label><div class="dj-cross-labels"><strong>A</strong><button type="button" class="text-btn" data-dj-action="center">${this.t('center')}</button><strong>B</strong></div><input id="dj-cross" type="range" min="0" max="100" step="1" value="${this.cross}" data-dj-control="cross"><div class="dj-both"><button type="button" class="btn secondary" data-dj-action="start-all">${this.t('startBoth')}</button><button type="button" class="text-btn" data-dj-action="pause-all">${this.t('pauseBoth')}</button></div></section><section class="dj-record"><p class="fineprint">${this.t('recordHint')}</p><button type="button" class="btn" data-dj-action="record">${this.t('record')}</button><span id="dj-record-state" role="status"></span><div class="dj-export" hidden><button type="button" class="btn secondary" data-dj-action="download">${this.t('download')}</button><button type="button" class="btn secondary" data-dj-action="save">${this.t('save')}</button></div></section>`;
  root.onclick=event=>{const button=event.target.closest('[data-dj-action]');if(button)this.action(button).catch(this.onError);};
  for(const d of Object.values(this.decks)){
    const details=root.querySelector(`[data-dj-deck="${d.key}"] details`);details.open=!!d.expanded;details.addEventListener('toggle',()=>{d.expanded=details.open;});
    root.querySelector(`[data-dj-title="${d.key}"]`).insertAdjacentHTML('afterend',`<meter class="dj-meter" min="0" max="1" value="0" aria-label="${d.key} level"></meter>`);
  }
  root.oninput=event=>{if(event.target.dataset.djControl)this.control(event.target);};
  this.bindWaves();this.bindProjects();clearInterval(this.timer);this.timer=setInterval(()=>this.update(),200);this.update();
 }
 async load(key,track){
  const d=this.decks[key];if(!d||d.loading)return;
  const revision=(d.loadRevision||0)+1;d.loadRevision=revision;d.alignRevision=(d.alignRevision||0)+1;d.aligning=false;d.loading=true;d.audio.pause();this.update();
  try{
   await this.ensure();
   const source=await this.getSource(track,{cancelled:()=>revision!==d.loadRevision||!this.active});if(!source||revision!==d.loadRevision)return;
   d.loopNode?.port.postMessage({type:'reset'});d.loopNode?.port.postMessage({type:'transport',playing:false,feeding:false});d.engine.resetPitch();
   if(d.blobUrl)URL.revokeObjectURL(d.blobUrl);d.blobUrl=source.url.startsWith('blob:')?source.url:null;
   d.track=source.track;d.audio.src=source.url;d.cues=[null,null,null];d.roll=0;d.loopBars=0;d.rollActive=false;d.bpm=0;d.offset=0;d.analysis=null;d.analysisError=false;d.analysing=false;d.gridEdited=false;d.taps=[];d.fx.restore();
   d.engine.inputPitchRatio=1;d.engine.setSpeed(d.speed);d.engine.setPitch(d.pitch);d.engine.setBass(d.bass);d.engine.setTreble(d.treble);
   this.notify(this.t('loaded'));this.remount();if(!d.track.local)this.analyse(d).catch(()=>{});return true;
  }finally{if(revision===d.loadRevision)d.loading=false;this.update();}
 }
 remount(){if(this.root?.isConnected)this.mount(this.root);}
 beat(d){return d.bpm?60/d.bpm:0;}
 snap(d,time){const beat=this.beat(d);return Math.max(0,Math.min(d.audio.duration||Infinity,beat?d.offset+Math.round((time-d.offset)/beat)*beat:time));}
 seek(d,time,{keepAlignment=false}={}){
  if(!keepAlignment){d.alignRevision=(d.alignRevision||0)+1;d.aligning=false;d.engine?.setSpeed(d.speed);}
  d.loopNode?.port.postMessage({type:'reset'});d.roll=0;d.loopBars=0;d.rollActive=false;this.syncRollRate(d);d.engine?.resetPitch();
  d.audio.currentTime=Math.max(0,Math.min(d.audio.duration||Infinity,time));
 }
 waveMarkup(d){return `<div class="dj-wave" data-wave="${d.key}" aria-label="${this.t('wave')}"><canvas height="100" width="1000"></canvas><span class="dj-wave-cursor"></span><span class="dj-wave-label">${this.t('wave')}</span></div><div class="dj-beat-strip" data-beat-strip="${d.key}" aria-hidden="true"><span></span></div><button type="button" class="text-btn dj-analysis" data-dj-action="analyse" data-deck="${d.key}">${this.t(d.analysing?'analysing':d.analysisError?'analysisRetry':d.bpm?'estimated':d.analysis?'uncertain':'analyse')}${d.bpm?' · '+d.bpm:''}</button>`;}
 bindWaves(){
  this.waveObserver?.disconnect();this.waveObserver=new ResizeObserver(()=>{for(const d of Object.values(this.decks))this.drawWave(d);});
  for(const d of Object.values(this.decks)){
   const wave=this.root.querySelector(`[data-wave="${d.key}"]`);this.waveObserver.observe(wave);
   wave.onclick=event=>{if(d.track&&Number.isFinite(d.audio.duration)){const box=wave.getBoundingClientRect();this.seek(d,d.audio.duration*Math.max(0,Math.min(1,(event.clientX-box.left)/box.width)));this.update();}};
   this.drawWave(d);
  }
 }
 drawWave(d){
  const wave=this.root?.querySelector(`[data-wave="${d.key}"]`);if(!wave)return;
  const canvas=wave.querySelector('canvas'),width=Math.max(100,Math.round(wave.clientWidth*Math.min(2,devicePixelRatio||1))),height=100;
  canvas.width=width;const ctx=canvas.getContext('2d');ctx.clearRect(0,0,width,height);
  const peaks=d.analysis?.peaks||[],duration=d.analysis?.duration||d.audio.duration||d.track?.duration||1;
  ctx.fillStyle=d.key==='A'?'#c9ff82':'#b7a5ff';
  for(let x=0;x<width;x+=3){const at=Math.floor(x/width*peaks.length),peak=peaks[at]||.025;const size=Math.max(2,Math.sqrt(peak)*77);ctx.globalAlpha=.8;ctx.fillRect(x,(height-size)/2,2,size);}
  ctx.globalAlpha=1;
    if(d.bpm){const beat=60/d.bpm,offset=((d.offset%beat)+beat)%beat,step=Math.max(1,Math.ceil(duration/beat/100));ctx.strokeStyle='#ffffff40';ctx.beginPath();for(let i=0;i<duration/beat;i+=step){const x=(offset+i*beat)/duration*width;ctx.moveTo(x,0);ctx.lineTo(x,i%4?8:17);}ctx.stroke();}
  d.cues.forEach((cue,index)=>{if(cue===null)return;const x=cue/duration*width;ctx.fillStyle='#fff';ctx.fillRect(x,0,2,height);ctx.font='11px sans-serif';ctx.fillText(String(index+1),x+4,27);});
  if(d.loopBars&&d.loopStart!==undefined){ctx.fillStyle='#ffffff20';ctx.fillRect(d.loopStart/duration*width,0,d.loopBars*4*60/d.bpm/duration*width,height);}
 }
 updateWaves(){
  for(const d of Object.values(this.decks)){
   const wave=this.root.querySelector(`[data-wave="${d.key}"]`);if(!wave)continue;
   const duration=d.analysis?.duration||d.audio.duration||d.track?.duration||1;
   let position=d.audio.currentTime;
   if(d.loopBars&&d.rollActive){const now=this.context.currentTime;if(d.loopTick!==undefined&&!d.audio.paused)d.loopElapsed=(d.loopElapsed||0)+(now-d.loopTick)*d.speed;d.loopTick=now;position=d.loopStart+(d.loopElapsed||0)%(d.loopBars*4*60/d.bpm);}
   wave.querySelector('.dj-wave-cursor').style.left=Math.max(0,Math.min(100,position/duration*100))+'%';
   const signature=[d.bpm,d.offset,...d.cues,d.loopBars].join(':');if(signature!==d.waveSignature){d.waveSignature=signature;this.drawWave(d);}
   const bpm=this.root.querySelector(`[data-dj-bpm="${d.key}"]`);bpm.textContent=d.bpm?Math.round(d.bpm*d.speed*10)/10+' BPM':'— BPM';
   const align=this.root.querySelector(`[data-dj-action="align"][data-deck="${d.key}"]`);align.disabled=!!d.aligning;align.textContent=d.aligning?(this.language()==='ru'?'Совмещаю…':'Aligning…'):this.t('align');
   const strip=this.root.querySelector(`[data-beat-strip="${d.key}"]`),beat=this.beat(d);
   strip.style.backgroundPositionX=beat?-((position-d.offset)/beat%4)*25+'%':'0';
   strip.classList.toggle('has-grid',!!beat);
   for(const button of this.root.querySelectorAll(`[data-dj-action="loop"][data-deck="${d.key}"]`))button.classList.toggle('active',!!d.loopBars&&Number(button.dataset.bars)===d.loopBars);
   const status=this.root.querySelector(`[data-loop-status="${d.key}"]`);status.textContent=d.loopBars?this.t(d.rollActive?'loopPlaying':'loopPending'):'';
   const analysis=this.root.querySelector(`.dj-analysis[data-deck="${d.key}"]`);analysis.textContent=this.t(d.analysing?'analysing':d.analysisError?'analysisRetry':d.bpm?'estimated':d.analysis?'uncertain':'analyse')+(d.bpm?' · '+d.bpm:'');analysis.disabled=d.analysing||!d.track;
   const echo=this.root.querySelector(`[data-dj-action="echo"][data-deck="${d.key}"]`);echo.textContent=this.t(d.fx?.out?'restore':'echo');echo.classList.toggle('active',!!d.fx?.out);
  }
 }
 async analyse(d){
  if(d.analysing||!d.track||d.track.local||this.demoKey)return;
  const track=d.track.id,revision=d.loadRevision;d.analysing=true;d.analysisError=false;this.update();
  const previous=this.analysisQueue||Promise.resolve();let release;this.analysisQueue=new Promise(resolve=>{release=resolve;});
  try{
   await previous;if(d.loadRevision!==revision)return;
   let data;
   for(let attempt=0;attempt<3;attempt++){
    try{data=await(await this.request('dj/analysis?track='+encodeURIComponent(track))).json();break;}
    catch(error){if(attempt===2)throw error;await new Promise(r=>setTimeout(r,1200*(attempt+1)));}
    if(d.loadRevision!==revision)return;
   }
   if(d.loadRevision!==revision)return;
   d.analysis=data;
   if(!d.gridEdited){d.bpm=data.bpm||0;d.offset=data.offset||0;}
   this.drawWave(d);
  }catch{if(d.loadRevision===revision)d.analysisError=true;}
  finally{release();if(d.loadRevision===revision)d.analysing=false;this.update();}
 }
 async extraAction(action,d,button){
  if(action==='analyse'){d.gridEdited=false;return this.analyse(d);}
  if(action==='echo'){if(d.fx.out)d.fx.restore();else d.fx.echoOut((d.bpm||120)*d.speed);this.update();return;}
  if(action==='reset-fx'){d.filter=0;d.bassCut=0;d.fx.set(0,0);d.fx.restore();this.remount();return;}
  if(action==='first-beat'){d.offset=d.audio.currentTime;d.gridEdited=true;this.update();return;}
  if(action==='half'||action==='double'){const bpm=d.bpm*(action==='half'?.5:2);if(bpm>=30&&bpm<=300){d.bpm=bpm;d.gridEdited=true;this.update();}return;}
  if(action==='align'){
   const other=this.decks[d.key==='A'?'B':'A'];if(!d.bpm||!other.bpm)return this.notify(this.t('needBpm'));
   const speed=other.bpm*other.speed/d.bpm;if(speed<.5||speed>2)return this.notify(this.t('needBpm'));
   d.speed=speed;d.engine.setSpeed(speed);
   const target=(lead=0)=>{const phase=(((other.audio.currentTime+lead*other.speed)-other.offset)/this.beat(other)%1+1)%1;const own=Math.floor((d.audio.currentTime-d.offset)/this.beat(d));return d.offset+(own+phase)*this.beat(d);};
   // Prepare only the follower. Commit its rate before seeking so a queued
   // mobile rate write cannot invalidate the newly aligned media position.
   const revision=(d.alignRevision||0)+1;d.alignRevision=revision;d.aligning=true;this.update();
   const wasPlaying=!d.audio.paused;d.engine.flushRate();
   const jump=position=>new Promise(resolve=>{const started=performance.now();let timer;const finish=()=>{clearTimeout(timer);d.audio.removeEventListener('seeked',finish);resolve((performance.now()-started)/1000);};d.audio.addEventListener('seeked',finish,{once:true});timer=setTimeout(finish,1500);this.seek(d,position,{keepAlignment:true});});
   try{
    await jump(target());
    let lead=0;
    for(let pass=0;pass<3&&this.active&&d.alignRevision===revision&&wasPlaying&&!other.audio.paused;pass++){
     await new Promise(resolve=>setTimeout(resolve,180));
     const a=((other.audio.currentTime-other.offset)/this.beat(other)%1+1)%1,b=((d.audio.currentTime-d.offset)/this.beat(d)%1+1)%1;
     const error=((a-b+1.5)%1)-.5;
     if(Math.abs(error)<.045)break;
     lead=Math.max(-.4,Math.min(.4,lead+error*this.beat(d)/speed));
     await jump(target(lead));
    }
   }finally{if(d.alignRevision===revision)d.aligning=false;}
   this.remount();return;
  }
  if(action==='loop'){
   if(!d.loopNode)return this.notify(this.t('unsupported'));
   const bars=Number(button.dataset.bars);
   if(!bars||d.loopBars===bars){d.loopBars=0;d.rollActive=false;d.loopNode.port.postMessage({type:'loop',seconds:0});this.syncRollRate(d);this.update();return;}
   if(!d.bpm)return this.notify(this.t('needBpm'));
   const beat=this.beat(d),seconds=bars*4*beat/d.speed;
   if(seconds>64)return this.notify(this.t('loopLong'));
   const start=d.offset+Math.ceil((d.audio.currentTime-d.offset)/beat)*beat;
   if(Number.isFinite(d.audio.duration)&&start+bars*4*beat>d.audio.duration)return this.notify(this.language()==='ru'?'До конца трека осталось меньше выбранной петли. Выбери меньше тактов или перемотай назад.':'Not enough audio remains. Choose fewer bars or seek earlier.');
   d.loopBars=bars;d.roll=0;d.rollActive=false;d.captureSpeed=d.speed;d.loopStart=start;d.loopElapsed=0;d.loopTick=undefined;
   // Allocate outside the audio thread; transfer ownership without copying PCM.
   const length=Math.round(seconds*this.context.sampleRate),buffers=[new ArrayBuffer(length*4),new ArrayBuffer(length*4)];
   d.loopNode.port.postMessage({type:'loop',seconds,delay:Math.max(0,(start-d.audio.currentTime)/d.speed),buffers},buffers);
   this.syncRollRate(d);this.drawWave(d);this.update();
  }
 }
 projectMarkup(){return `<section class="dj-projects"><div class="dj-project-head"><div><small>SWIDJ / SET</small><strong>${escape(this.projectName)||this.t('project')}</strong></div><button type="button" class="chip" data-dj-action="project-save">${this.t('projectSave')}</button></div><details id="dj-project-list"><summary>${this.t('project')}</summary><p class="fineprint">${this.t('projectHint')}</p><div id="dj-project-items"></div><button type="button" class="text-btn" data-dj-action="project-new">${this.t('projectNew')}</button></details></section>`;}
 bindProjects(){
  const details=this.root.querySelector('#dj-project-list');details.addEventListener('toggle',()=>{if(details.open)this.refreshProjects().catch(this.onError);});
  this.renderProjects();
 }
 renderProjects(){
  const list=this.root?.querySelector('#dj-project-items');if(!list)return;
  list.innerHTML=(this.projects||[]).map(item=>`<div class="dj-project-row"><button type="button" class="preset-apply" data-dj-action="project-open" data-project="${escape(item.id)}">${escape(item.name)}<small>${Object.values(item.decks).map(d=>d.track?.title).filter(Boolean).map(escape).join(' · ')}</small></button><button type="button" class="icon-btn" data-dj-action="project-delete" data-project="${escape(item.id)}" aria-label="${this.t('projectDelete')}">×</button></div>`).join('')||`<p class="fineprint">${this.t('projectEmpty')}</p>`;
 }
 async projectRequest(payload){
  if(this.demoKey){let items=[];try{items=JSON.parse(localStorage.getItem(this.demoKey)||'[]');}catch{}
   if(payload?.action==='remove')items=items.filter(p=>p.id!==payload.id);
   if(payload?.action==='save'){const item={...payload.project,id:payload.id||crypto.randomUUID(),name:payload.name};for(const [key,d] of Object.entries(item.decks))d.track=this.decks[key].track;items=[...items.filter(p=>p.id!==item.id),item];}
   if(payload)localStorage.setItem(this.demoKey,JSON.stringify(items));return {projects:items};
  }
  return (await this.request('dj/projects',payload)).json();
 }
 async refreshProjects(){this.projects=(await this.projectRequest()).projects;this.renderProjects();}
 ask(title,withName=false){
  return new Promise(resolve=>{
   this.openDialog(title,withName?`<label for="dj-project-name">${this.t('projectName')}</label><input id="dj-project-name" maxlength="50" required value="${escape(this.projectName)}" autocomplete="off">`:'',`<button type="button" value="cancel" class="text-btn">${this.t('cancel')}</button><button value="confirm" class="btn">${this.t('confirm')}</button>`);
   const dialog=document.querySelector('#dialog'),form=document.querySelector('#dialog-form');let settled=false;
   const done=value=>{if(settled)return;settled=true;form.onsubmit=null;dialog.removeEventListener('close',closed);resolve(value);};
   const closed=()=>done(null);dialog.addEventListener('close',closed);
   form.querySelector('#dialog-actions [value="cancel"]').onclick=()=>dialog.close();
   form.onsubmit=event=>{event.preventDefault();const value=event.submitter?.value==='confirm'?(withName?document.querySelector('#dj-project-name').value.trim():true):null;done(value);dialog.close();};
   if(withName){const input=document.querySelector('#dj-project-name');input.onkeydown=event=>{if(event.key==='Enter'){event.preventDefault();form.requestSubmit(form.querySelector('[value="confirm"]'));}};input.focus();}
  });
 }
 async projectAction(action,id){
  if(this.projectBusy)return;
  if(action==='project-save'||action==='project-new'){
   if(!Object.values(this.decks).some(d=>d.track))return this.notify(this.t('choose'));
   if(Object.values(this.decks).some(d=>d.track?.local))return this.notify(this.t('projectLocal'));
   const name=await this.ask(this.t('projectSave'),true);if(!name)return;
   const project={cross:this.cross,decks:{}};
   for(const [key,d] of Object.entries(this.decks))project.decks[key]={track:d.track?.id||null,position:d.audio.currentTime,speed:d.speed,pitch:d.pitch,volume:d.volume,bass:d.bass,treble:d.treble,bpm:d.bpm,offset:d.offset,filter:d.filter,bassCut:d.bassCut,cues:[...d.cues]};
   this.projectBusy=true;
   try{this.projects=(await this.projectRequest({action:'save',id:action==='project-new'?'':this.projectId,name,project})).projects;const item=this.projects.find(p=>p.id===this.projectId&&action!=='project-new')||this.projects.at(-1);this.projectId=item.id;this.projectName=item.name;this.remount();this.notify(this.t('projectSaved'));}finally{this.projectBusy=false;}
   return;
  }
  await this.refreshProjects();const item=this.projects.find(p=>p.id===id);if(!item)return;
  if(!await this.ask(this.t(action==='project-delete'?'confirmDelete':'confirmLoad')))return;
  this.projectBusy=true;
  try{
   if(action==='project-delete'){this.projects=(await this.projectRequest({action:'remove',id})).projects;if(this.projectId===id){this.projectId='';this.projectName='';}this.remount();return;}
   for(const d of Object.values(this.decks))d.audio.pause();
   if(this.recorder?.state==='recording'){this.recordFinishing=true;this.recorder.stop();}
   const active=()=>this.active&&this.root?.isConnected;
   for(const key of ['A','B']){
    if(!active())return;
    const saved=item.decks[key],d=this.decks[key];
    if(saved.track){if(!await this.load(key,saved.track)||!active())return;}
    else {d.audio.removeAttribute('src');d.audio.load();d.track=null;d.analysis=null;d.rollActive=false;d.loopNode?.port.postMessage({type:'reset'});if(d.engine)d.engine.inputPitchRatio=1;}
    for(const field of ['speed','pitch','volume','bass','treble','bpm','offset','filter','bassCut'])d[field]=saved[field];
    d.gridEdited=true;d.cues=[...saved.cues];d.loopBars=0;d.roll=0;
    if(d.engine){d.engine.setSpeed(d.speed);d.engine.setPitch(d.pitch);d.engine.setBass(d.bass);d.engine.setTreble(d.treble);d.fx.set(d.filter,d.bassCut);d.fx.restore();}
    if(saved.track){if(d.audio.readyState<1)await new Promise(resolve=>{const timer=setTimeout(resolve,10000);d.audio.addEventListener('loadedmetadata',()=>{clearTimeout(timer);resolve();},{once:true});});if(!active())return;this.seek(d,saved.position);}
   }
   this.setCross(item.cross);this.projectId=item.id;this.projectName=item.name;this.remount();this.notify(this.t('projectLoaded'));
  }finally{this.projectBusy=false;}
 }
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
   this.seek(d,d.audio.duration*value/1000);return;
  }
  if(key==='bpm'){d.bpm=value>=30&&value<=300?value:0;d.gridEdited=true;d.alignRevision=(d.alignRevision||0)+1;d.aligning=false;d.engine?.setSpeed(d.speed);if(d.loopBars){d.loopBars=0;d.rollActive=false;d.loopNode?.port.postMessage({type:'loop',seconds:0});this.syncRollRate(d);}this.update();return;}
  d[key]=value;
  const output=this.root?.querySelector(`[data-dj-output="${d.key}:${key}"]`);if(output)output.textContent=this.formatControl(key,value);
  if(key==='volume')this.setCross(this.cross);
  if(key==='speed'){d.alignRevision=(d.alignRevision||0)+1;d.aligning=false;d.engine?.setSpeed(value);this.syncRollRate(d);}
  if(key==='pitch')d.engine?.setPitch(value);
  if(key==='bass')d.engine?.setBass(value);
  if(key==='treble')d.engine?.setTreble(value);
  if(key==='filter'||key==='bassCut')d.fx?.set(d.filter,d.bassCut);
 }
 async play(d){if(!d.track)return this.notify(this.t('choose'));await this.ensure();await d.engine.unlock();this.pauseMain();if(d.fx?.out)d.fx.restore();await d.audio.play();}
 async action(button){
  const action=button.dataset.djAction,d=this.decks[button.dataset.deck];
  if(action==='focus'){this.focusDeck=d.key;this.root.dataset.focus=d.key;for(const b of this.root.querySelectorAll('[data-dj-action=focus]'))b.setAttribute('aria-pressed',String(b.dataset.deck===d.key));this.drawWave(d);return;}
  if(action.startsWith('project-'))return this.projectAction(action,button.dataset.project);
  if(action==='load')return this.choose(d.key);
  if(action==='center'){this.setCross(50);this.root.querySelector('#dj-cross').value=50;return;}
  if(action==='pause-all'){for(const deck of Object.values(this.decks))deck.audio.pause();return;}
  if(action==='start-all'){await this.ensure();await Promise.all(Object.values(this.decks).filter(deck=>deck.track).map(deck=>this.play(deck)));return;}
  if(action==='record')return this.toggleRecording();
  if(action==='download'||action==='save')return this.deliver(action);
  if(!d)return;
  if(action==='play'){if(d.audio.paused)await this.play(d);else d.audio.pause();return;}
  if(!d.track)return this.notify(this.t('choose'));
  if(['loop','align','first-beat','half','double','analyse','echo','reset-fx'].includes(action))return this.extraAction(action,d,button);
  if(action==='cue'){
   const index=Number(button.dataset.cue);
   if(d.cues[index]===null){d.cues[index]=this.snap(d,d.audio.currentTime);this.notify(this.t('cueSaved'));}
   else this.seek(d,d.cues[index]);
   this.update();return;
  }
  if(action==='clear-cues'){d.cues=[null,null,null];this.update();return;}
  if(action==='roll'){
   if(!d.loopNode)return this.notify(this.t('unsupported'));
   d.loopBars=0;d.roll=d.roll===Number(button.dataset.seconds)?0:Number(button.dataset.seconds);d.loopNode.port.postMessage({type:'roll',seconds:d.roll});this.update();return;
  }
  if(action==='tap'){
   const now=performance.now();if(now-(d.taps.at(-1)||0)>2000)d.taps=[];
   d.taps.push(now);d.taps=d.taps.slice(-6);
   if(d.taps.length>1){const bpm=60000*(d.taps.length-1)/(d.taps.at(-1)-d.taps[0]);if(bpm>=30&&bpm<=300)d.bpm=Math.round(bpm*10)/10;}
   d.gridEdited=true;d.offset=d.audio.currentTime%(60/(d.bpm||120));this.update();return;
  }
  if(action==='sync'){
   const other=this.decks[d.key==='A'?'B':'A'];if(!d.bpm||!other.bpm)return this.notify(this.t('needBpm'));
   const speed=other.bpm*other.speed/d.bpm;
   if(speed<.5||speed>2)return this.notify(this.language()==='ru'?'Темпы слишком разные для такого перехода. Попробуй другой трек.':'These tempos are too far apart for this transition. Try another track.');
   d.speed=speed;d.engine.setSpeed(d.speed);this.syncRollRate(d);this.remount();return;
  }
  if(action==='reset'){d.speed=1;d.pitch=0;d.bass=0;d.treble=0;d.volume=.85;d.filter=0;d.bassCut=0;d.fx?.set(0,0);d.fx?.restore();d.engine.setPitch(0);d.engine.setSpeed(1);d.engine.setBass(0);d.engine.setTreble(0);this.syncRollRate(d);this.setCross(this.cross);this.remount();}
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
  this.updateWaves();
  const recording=this.recorder?.state==='recording';
  const button=this.root.querySelector('[data-dj-action="record"]');button.textContent=this.t(recording?'stop':'record');button.classList.toggle('recording',recording);button.disabled=this.busy;
  this.root.querySelector('#dj-record-state').textContent=this.busy?this.t('working'):recording?this.t('recording')+' · '+stamp((Date.now()-this.recordStarted)/1000):this.recorded?this.t('ready'):'';
  this.root.querySelector('.dj-export').hidden=!this.recorded||recording;
  for(const action of this.root.querySelectorAll('.dj-export button'))action.disabled=this.busy;
 }
 pauseAll(){this.active=false;for(const d of Object.values(this.decks)){d.loadRevision=(d.loadRevision||0)+1;d.loading=false;d.analysing=false;d.alignRevision=(d.alignRevision||0)+1;d.aligning=false;d.engine?.setSpeed(d.speed);d.audio.pause();}if(this.recorder?.state==='recording'){this.recordFinishing=true;this.recorder.stop();}clearInterval(this.timer);this.waveObserver?.disconnect();}
}
