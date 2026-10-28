import {drawScene} from './scene.js';
const storage={get:key=>{try{return localStorage.getItem(key);}catch{return null;}},set:(key,value)=>{try{localStorage.setItem(key,value);}catch{}}};
const $=id=>document.getElementById(id);
const words={ru:{eyebrow:'ТВОЯ МУЗЫКА. ТВОЁ ДВИЖЕНИЕ.',heading:'Звук становится видимым.',intro:'Собери оформление, которое чувствует твою музыку.',source:'01 / Музыка и изображения',music:'Выбрать музыку',noAudio:'Аудиофайл не выбран',backgroundFile:'Фон: картинка / видео',logoFile:'Картинка / логотип в центре',clear:'Убрать',mutedBackground:'Фоновое видео всегда без своего звука.',prepare:'Подготовить предпросмотр',presets:'02 / Готовые оформления',scene:'03 / Твоё оформление',background:'Фон',gradient:'Градиент',image:'Картинка',video:'Видео',shape:'Фигура',circle:'Круг',triangle:'Треугольник',square:'Квадрат',none:'Без фигуры',spectrum:'Спектр',ring:'Кольцо',bars:'Полоски',wave:'Волна',off:'Выключено',accent:'Акцент',secondColor:'Второй цвет',baseColor:'Основа',particles:'Частицы',stars:'Звёзды',sparks:'Искры',snow:'Снег',title:'Название',subtitle:'Подпись / автор',savePreset:'Сохранить настройки',loadPreset:'Вернуть настройки',emptyPreview:'Начни со своей музыки',emptyHint:'Фон и логотип можно добавить или оставить пустыми.',exportEyebrow:'ГОТОВЫЙ РОЛИК',export:'Экспорт видео',aspect:'Формат',resolution:'Качество',fps:'Кадры/с',start:'Начало, секунды',end:'Конец, 0 — весь трек',renderNote:'Окончательное видео собирается отдельно. Можно продолжать пользоваться остальным приложением.',render:'Создать MP4',cancel:'Отменить',download:'Скачать видео',previewNote:'Предпросмотр адаптируется к экрану. Выбранные разрешение и FPS относятся к готовому видео.',particleCount:'Количество частиц',strength:'Сила реакции',glow:'Свечение',rotation:'Вращение',dim:'Затемнение фона',zoom:'Движение фона',chooseAudio:'Сначала выбери аудиофайл.',changed:'Файлы изменились. Подготовь предпросмотр заново.',uploading:'Загружаю файлы…',queued:'В очереди',analysis:'Анализирую музыку и готовлю фон…',ready:'Готово. Можно слушать и менять оформление.',rendering:'Создаю видео',complete:'Видео готово. Настройки этого экспорта сохранены отдельно.',cancelled:'Задание отменено.',failed:'Не удалось подготовить файл. Проверь формат и попробуй ещё раз.',saved:'Настройки сохранены на этом устройстве.',loaded:'Настройки восстановлены. Изображения и музыку загрузи отдельно.',missingPreset:'На этом устройстве ещё нет сохранённых настроек.',error:'Не удалось выполнить действие.',local:'ЛОКАЛЬНАЯ ТЕСТОВАЯ ВЕРСИЯ',featureWait:'Подготавливаю данные для предпросмотра…',snapshot:'Изменения после запуска экспорта попадут в следующий ролик.'},
en:{eyebrow:'YOUR MUSIC. YOUR MOTION.',heading:'Make your sound visible.',intro:'Create a visual world that responds to your music.',source:'01 / Music and images',music:'Choose music',noAudio:'No audio selected',backgroundFile:'Background: image / video',logoFile:'Center image / channel logo',clear:'Remove',mutedBackground:'Background video is always muted.',prepare:'Prepare preview',presets:'02 / Visual presets',scene:'03 / Make it yours',background:'Background',gradient:'Gradient',image:'Image',video:'Video',shape:'Shape',circle:'Circle',triangle:'Triangle',square:'Square',none:'No shape',spectrum:'Spectrum',ring:'Ring',bars:'Bars',wave:'Wave',off:'Off',accent:'Accent',secondColor:'Second color',baseColor:'Base color',particles:'Particles',stars:'Stars',sparks:'Sparks',snow:'Snow',title:'Title',subtitle:'Caption / artist',savePreset:'Save settings',loadPreset:'Restore settings',emptyPreview:'Start with your music',emptyHint:'Add a background and logo, or keep them empty.',exportEyebrow:'YOUR FINISHED VIDEO',export:'Export video',aspect:'Format',resolution:'Quality',fps:'Frame rate',start:'Start, seconds',end:'End, 0 means full track',renderNote:'Final video is rendered separately. You can keep using the rest of the app.',render:'Create MP4',cancel:'Cancel',download:'Download video',previewNote:'Preview adapts to your screen. Selected resolution and FPS apply to the exported video.',particleCount:'Particle count',strength:'Music response',glow:'Glow',rotation:'Rotation',dim:'Background dimming',zoom:'Background motion',chooseAudio:'Choose an audio file first.',changed:'Files changed. Prepare the preview again.',uploading:'Uploading files…',queued:'Queued',analysis:'Analysing music and preparing the background…',ready:'Ready. Play your music and explore the controls.',rendering:'Rendering video',complete:'Video ready. Its export settings were saved separately.',cancelled:'Task cancelled.',failed:'Could not prepare this file. Check the format and try again.',saved:'Settings saved on this device.',loaded:'Settings restored. Load your images and audio separately.',missingPreset:'No saved settings on this device yet.',error:'Could not complete the action.',local:'LOCAL TEST BUILD',featureWait:'Preparing preview data…',snapshot:'Changes after export starts will apply to the next video.'}};
Object.assign(words.ru,{history:'Мои готовые ролики',historyEmpty:'Здесь появятся твои видео. Файлы хранятся временно — сохраняй готовые результаты.',downloadFallback:'Нажми ссылку ещё раз, чтобы скачать через браузер.'});
Object.assign(words.en,{history:'My videos',historyEmpty:'Your videos will appear here. Files are temporary — download the results you want to keep.',downloadFallback:'Tap the link again to download using your browser.'});
let language=new URLSearchParams(location.search).get('lang')||storage.get('swidj-video-language')||'ru';if(!words[language])language='ru';
const t=key=>words[language][key]||key;
const ids=['backgroundKind','shape','spectrum','particles','color','color2','background','particleCount','strength','glow','rotation','dim','zoom','title','subtitle','aspect','resolution','fps','start','end'];
const numeric=new Set(['particleCount','strength','glow','rotation','dim','zoom','resolution','fps','start','end']);
let config,scene,draft=null,renderJob=null,pollTimer,revision=0,featureBlock=null,featureRequest=0,featuresBusy=false,lastDraw=0,selectedAudio=null;
const assets={},audio=$('audio'),video=$('video-background'),canvas=$('canvas'),ctx=canvas.getContext('2d');
let historyTimer;
let telegramData='';try{telegramData=window.parent.Telegram?.WebApp?.initData||'';}catch{}
async function api(path,options={}){
 const response=await fetch('api/'+path,{...options,headers:{'X-SwiDJ-Local':'1','X-Telegram-Init-Data':telegramData,...options.headers}});
 if(!response.ok)throw new Error(String(response.status));return response.json();
}
function notice(key){$('notice').textContent=t(key);}
function nativeDownload(event){
 let telegram;try{telegram=window.parent.Telegram?.WebApp;}catch{}
 const link=event.currentTarget;
 if(link.dataset.nativeFailed||typeof telegram?.downloadFile!=='function')return;
 event.preventDefault();
 try{telegram.downloadFile({url:link.href,file_name:(link.download||'SwiDJ.mp4').replace(/[\\/:*?"<>|]/g,'').replace(/\.mp4$/i,'').slice(0,96)+'.mp4'},accepted=>{if(!accepted){link.dataset.nativeFailed='1';notice('downloadFallback');}});}
 catch{link.dataset.nativeFailed='1';notice('downloadFallback');}
}
async function refreshHistory(){
 clearTimeout(historyTimer);
 try{
  const data=await api('history'),list=$('history-list');list.replaceChildren();
  if(!data.jobs.length){const note=document.createElement('p');note.className='note';note.textContent=t('historyEmpty');list.append(note);}
  for(const job of data.jobs){
   const row=document.createElement('div');row.className='history-item';const text=document.createElement('span');text.textContent=job.scene?.title||'SwiDJ';row.append(text);
   if(job.state==='complete'&&job.files?.result){const link=document.createElement('a');link.href=job.files.result;link.download=(job.scene?.title||'SwiDJ')+'.mp4';link.className='button secondary';link.textContent=t('download');link.onclick=nativeDownload;row.append(link);}
   else{const status=document.createElement('small');status.textContent=t(({queued:'queued',render:'rendering',failed:'failed',cancelled:'cancelled',interrupted:'failed'})[job.state]||'queued');row.append(status);}
   list.append(row);
  }
  if(data.jobs.some(job=>['queued','render'].includes(job.state)))historyTimer=setTimeout(()=>{if(!document.hidden)refreshHistory();},5000);
 }catch{}
}
function translate(){document.documentElement.lang=language;for(const element of document.querySelectorAll('[data-i18n]'))element.textContent=t(element.dataset.i18n);$('language').textContent=language==='ru'?'EN':'RU';if(config?.dev)$('environment').textContent=t('local');for(const element of document.querySelectorAll('[data-slider]'))element.textContent=t(element.dataset.slider);}
function sync(){for(const id of ids)if($(id))$(id).value=scene[id];for(const output of document.querySelectorAll('[data-output]'))output.textContent=String(scene[output.dataset.output]);for(const button of document.querySelectorAll('[data-preset]'))button.setAttribute('aria-pressed',String(scene.preset===button.dataset.preset));resize();draw();}
function resize(){const ratio=scene.aspect==='portrait'?9/16:scene.aspect==='square'?1:16/9;const width=Math.min(960,Math.max(280,canvas.parentElement.clientWidth));canvas.width=Math.round(width);canvas.height=Math.round(width/ratio);}
function clock(seconds){return `${Math.floor(seconds/60)}:${String(Math.floor(seconds%60)).padStart(2,'0')}`;}
function endTime(){return draft?Math.min(scene.end||draft.duration,draft.duration):0;}
function read(){for(const id of ids){const node=$(id);if(node)scene[id]=numeric.has(id)?Number(node.value):node.value;}for(const output of document.querySelectorAll('[data-output]'))output.textContent=String(scene[output.dataset.output]);resize();draw();}
function interpolate(time){
 if(!featureBlock)return new Array(53).fill(0);
 const pos=time*featureBlock.rate-featureBlock.offset;if(pos<0||pos>=featureBlock.values.length)return new Array(53).fill(0);
 const i=Math.floor(pos),a=featureBlock.values[i],b=featureBlock.values[Math.min(i+1,featureBlock.values.length-1)],f=pos-i;return a.map((v,n)=>v*(1-f)+b[n]*f);
}
async function loadFeatures(time){
 if(!draft||featuresBusy)return;
 const local=time*30-(featureBlock?.offset||0);
 if(featureBlock&&local>=0&&local<featureBlock.values.length&&(featureBlock.values.length<1800||local<featureBlock.values.length-150))return;
 featuresBusy=true;const ticket=++featureRequest,id=draft.id;
 try{const block=await api(`features/${id}?start=${Math.max(0,time-3)}`);if(draft?.id===id&&ticket===featureRequest){featureBlock=block;draw();}}catch{if(draft?.id===id)notice('error');}finally{if(ticket===featureRequest)featuresBusy=false;}
}
function draw(){if(!scene)return;drawScene(ctx,canvas.width,canvas.height,scene,Math.max(0,audio.currentTime-scene.start),interpolate(audio.currentTime),assets);}
function tick(timestamp){
 if(!audio.paused&&timestamp-lastDraw>1000/30){lastDraw=timestamp;draw();$('seek').value=audio.currentTime;$('clock').textContent=clock(audio.currentTime)+' / '+clock(draft?.duration||0);loadFeatures(audio.currentTime);if(audio.currentTime>=endTime())pause();}
 requestAnimationFrame(tick);
}
function pause(){audio.pause();video.pause();$('play').textContent='▶';}
async function play(){
 if(!draft)return;
 if(!audio.paused)return pause();
 if(audio.currentTime<scene.start||audio.currentTime>=endTime())audio.currentTime=scene.start;
 loadFeatures(audio.currentTime);video.muted=true;
 if(scene.backgroundKind==='video'&&assets.video){if(Number.isFinite(video.duration)&&video.duration>0)video.currentTime=(audio.currentTime-scene.start)%video.duration;try{await video.play();}catch{notice('error');}}
 await audio.play();$('play').textContent='Ⅱ';
}
function image(url){return new Promise((resolve,reject)=>{const img=new Image();img.onload=()=>resolve(img);img.onerror=reject;img.src=url;});}
async function ready(job){
 draft=job;featureBlock=null;featureRequest++;featuresBusy=false;audio.src=job.files.audio;
 if(job.files['background-image'])assets.background=await image(job.files['background-image']);else delete assets.background;
 if(job.files.logo)assets.logo=await image(job.files.logo);else delete assets.logo;
 if(job.files['background-video']){video.src=job.files['background-video'];video.load();assets.video=video;}else{video.removeAttribute('src');video.load();delete assets.video;}
 scene.backgroundKind=job.backgroundKind;sync();await loadFeatures(scene.start);$('empty-preview').hidden=true;
 $('play').disabled=$('seek').disabled=$('restart').disabled=$('render').disabled=false;$('seek').max=job.duration;$('clock').textContent='0:00 / '+clock(job.duration);notice('ready');draw();
}
function fileChanged(){revision++;pause();draft=null;featureBlock=null;featureRequest++;featuresBusy=false;$('play').disabled=$('seek').disabled=$('restart').disabled=$('render').disabled=true;notice('changed');}
async function prepare(){
 const file=selectedAudio||$('audio-file').files[0];if(!file)return notice('chooseAudio');
 pause();const form=new FormData();form.append('audio',file,file.name||'studio-mix.wav');
 for(const name of ['background','logo'])if($(name+'-file').files[0])form.append(name,$(name+'-file').files[0]);
 const ticket=revision;$('prepare').disabled=true;notice('uploading');
 try{let job=await api('drafts',{method:'POST',body:form});$('cancel').hidden=false;renderJob=job;
  while(['queued','analysis','upload'].includes(job.state)){
   if(ticket!==revision){await api('cancel/'+job.id,{method:'POST'});return;}
   notice(job.state==='queued'?'queued':'analysis');await new Promise(resolve=>setTimeout(resolve,700));job=await api('jobs/'+job.id);renderJob=job;
  }
  if(job.state==='ready'&&ticket===revision)await ready(job);else notice(job.state==='cancelled'?'cancelled':'failed');
 }catch{notice('error');}finally{$('prepare').disabled=false;$('cancel').hidden=true;renderJob=null;}
}
async function render(){
 if(!draft)return;read();if(!Number.isFinite(scene.start)||!Number.isFinite(scene.end)||scene.start>=draft.duration||scene.end&&scene.end<=scene.start)return notice('error');
 $('render').disabled=true;$('prepare').disabled=true;$('download').hidden=true;$('progress').hidden=false;$('cancel').hidden=false;
 try{
  let job=await api('render/'+draft.id,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(scene)});renderJob=job;
  while(['queued','render'].includes(job.state)){
   $('render-status').textContent=(job.state==='queued'?t('queued')+' · '+(job.position||1):t('rendering')+' · '+Math.round((job.progress||0)*100)+'%')+' — '+t('snapshot');
   $('progress').value=job.progress||0;await new Promise(resolve=>setTimeout(resolve,800));job=await api('jobs/'+job.id);renderJob=job;
  }
  if(job.state==='complete'){$('download').href=job.files.result;$('download').download=(job.scene.title||'SwiDJ')+'.mp4';$('download').hidden=false;$('progress').value=1;$('render-status').textContent=t('complete');}
  else $('render-status').textContent=t(job.state==='cancelled'?'cancelled':'failed');
 }catch{$('render-status').textContent=t('error');}finally{$('render').disabled=!draft;$('prepare').disabled=false;$('cancel').hidden=true;renderJob=null;refreshHistory();}
}
async function init(){
 config=await api('config');scene={...config.defaults};
 const controls=[['strength',0,3,.05],['glow',0,1,.05],['particleCount',0,200,1],['rotation',-1,1,.05],['dim',0,.95,.05],['zoom',1,1.5,.01]];
 for(const [key,min,max,step] of controls){const label=document.createElement('label');const line=document.createElement('span');line.className='slider-label';const text=document.createElement('span');text.dataset.slider=key;const output=document.createElement('output');output.dataset.output=key;line.append(text,output);const input=document.createElement('input');Object.assign(input,{type:'range',id:key,min,max,step});label.append(line,input);$('sliders').append(label);}
 const names={neon:'Neon Orbit',prism:'Prism',stars:'Starfield',minimal:'Minimal',retro:'Retro',liquid:'Liquid',stage:'Stage',photo:'Photo Motion'};
 for(const [key,value] of Object.entries(config.presets)){const button=document.createElement('button');button.type='button';button.className='preset';button.dataset.preset=key;button.textContent=names[key];button.style.setProperty('--a',value.color||'#334b57');button.style.setProperty('--b',value.color2||'#121b2c');button.onclick=()=>{scene={...scene,...value,preset:key};sync();};$('presets').append(button);}
 const history=document.createElement('details');history.className='panel history-panel';const summary=document.createElement('summary');summary.dataset.i18n='history';summary.textContent=t('history');const historyList=document.createElement('div');historyList.id='history-list';history.append(summary,historyList);document.querySelector('.footer-note').before(history);history.ontoggle=()=>{if(history.open)refreshHistory();};
 translate();sync();requestAnimationFrame(tick);refreshHistory();$('download').onclick=nativeDownload;
 for(const id of ids)$(id).addEventListener('input',read);
 $('language').onclick=()=>{language=language==='ru'?'en':'ru';storage.set('swidj-video-language',language);translate();refreshHistory();};
 $('audio-file').onchange=()=>{selectedAudio=$('audio-file').files[0]||null;$('audio-name').textContent=selectedAudio?.name||t('noAudio');if(selectedAudio&&!scene.title){scene.title=selectedAudio.name.replace(/\.[^.]+$/,'').slice(0,120);sync();}fileChanged();};
 for(const name of ['background','logo']){$(name+'-file').onchange=fileChanged;$('remove-'+name).onclick=()=>{$(name+'-file').value='';fileChanged();};}
 $('prepare').onclick=prepare;$('render').onclick=render;$('play').onclick=()=>play().catch(()=>notice('error'));
 $('restart').onclick=()=>{audio.currentTime=scene.start;loadFeatures(scene.start).then(draw);if(assets.video)video.currentTime=0;};
 $('seek').oninput=()=>{audio.currentTime=Number($('seek').value);if(assets.video&&video.duration)video.currentTime=Math.max(0,audio.currentTime-scene.start)%video.duration;loadFeatures(audio.currentTime).then(draw);$('clock').textContent=clock(audio.currentTime)+' / '+clock(draft.duration);};
 $('cancel').onclick=async()=>{if(renderJob)try{await api('cancel/'+renderJob.id,{method:'POST'});}catch{notice('error');}};
 $('save-preset').onclick=()=>{read();storage.set('swidj-video-preset:'+config.profile,JSON.stringify(scene));notice('saved');};
 $('load-preset').onclick=()=>{try{const saved=JSON.parse(storage.get('swidj-video-preset:'+config.profile));if(!saved)return notice('missingPreset');for(const key of ids)if(key in saved){if(numeric.has(key)){if(!Number.isFinite(saved[key]))continue;const field=$(key);scene[key]=Math.max(Number(field.min||0),Math.min(Number(field.max||86400),saved[key]));}else if(typeof saved[key]==='string')scene[key]=saved[key].slice(0,key==='title'?120:100);}sync();notice('loaded');}catch{notice('error');}};
 window.addEventListener('resize',()=>{resize();draw();});document.addEventListener('visibilitychange',()=>{if(document.hidden)pause();});audio.onended=pause;
 window.addEventListener('message',event=>{if(event.origin!==location.origin||event.source!==window.parent||event.data?.type!=='swidj:music-video'||!(event.data.audio instanceof Blob))return;selectedAudio=event.data.audio;$('audio-name').textContent=event.data.title||'Studio mix';scene.title=(event.data.title||scene.title).slice(0,120);if(words[event.data.language]){language=event.data.language;translate();}fileChanged();sync();});
 if(window.parent!==window)window.parent.postMessage({type:'swidj:music-video-ready'},location.origin);
}
init().catch(()=>notice('error'));
