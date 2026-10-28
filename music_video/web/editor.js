import {drawScene} from './scene.js';
import {ranges,normalize,presetScene,SceneHistory} from './state.js';
const storage={get:key=>{try{return localStorage.getItem(key);}catch{return null;}},set:(key,value)=>{try{localStorage.setItem(key,value);return true;}catch{return false;}}};
const $=id=>document.getElementById(id);
const words={ru:{eyebrow:'ТВОЯ МУЗЫКА. ТВОЁ ДВИЖЕНИЕ.',heading:'Звук становится видимым.',intro:'Собери оформление, которое чувствует твою музыку.',source:'01 / Музыка и изображения',music:'Выбрать музыку',noAudio:'Аудиофайл не выбран',backgroundFile:'Фон: картинка / видео',logoFile:'Картинка / логотип в центре',clear:'Убрать',mutedBackground:'Фоновое видео всегда без своего звука.',prepare:'Подготовить предпросмотр',presets:'02 / Готовые оформления',scene:'03 / Твоё оформление',background:'Фон',gradient:'Градиент',image:'Картинка',video:'Видео',shape:'Фигура',circle:'Круг',triangle:'Треугольник',square:'Квадрат',none:'Без фигуры',spectrum:'Спектр',ring:'Кольцо',bars:'Полоски',wave:'Волна',off:'Выключено',accent:'Акцент',secondColor:'Второй цвет',baseColor:'Основа',particles:'Частицы',stars:'Звёзды',sparks:'Искры',snow:'Снег',title:'Название',subtitle:'Подпись / автор',savePreset:'Сохранить настройки',loadPreset:'Вернуть настройки',emptyPreview:'Начни со своей музыки',emptyHint:'Фон и логотип можно добавить или оставить пустыми.',exportEyebrow:'ГОТОВЫЙ РОЛИК',export:'Экспорт видео',aspect:'Формат',resolution:'Качество',fps:'Кадры/с',start:'Начало, секунды',end:'Конец, 0 — весь трек',renderNote:'Окончательное видео собирается отдельно. Можно продолжать пользоваться остальным приложением.',render:'Создать MP4',cancel:'Отменить',download:'Скачать видео',previewNote:'Предпросмотр адаптируется к экрану. Выбранные разрешение и FPS относятся к готовому видео.',particleCount:'Количество частиц',strength:'Сила реакции',glow:'Свечение',rotation:'Вращение',dim:'Затемнение фона',zoom:'Движение фона',chooseAudio:'Сначала выбери аудиофайл.',changed:'Файлы изменились. Подготовь предпросмотр заново.',uploading:'Загружаю файлы…',queued:'В очереди',analysis:'Анализирую музыку и готовлю фон…',ready:'Готово. Можно слушать и менять оформление.',rendering:'Создаю видео',complete:'Видео готово. Настройки этого экспорта сохранены отдельно.',cancelled:'Задание отменено.',failed:'Не удалось подготовить файл. Проверь формат и попробуй ещё раз.',saved:'Настройки сохранены на этом устройстве.',loaded:'Настройки восстановлены. Изображения и музыку загрузи отдельно.',missingPreset:'На этом устройстве ещё нет сохранённых настроек.',error:'Не удалось выполнить действие.',local:'ЛОКАЛЬНАЯ ТЕСТОВАЯ ВЕРСИЯ',featureWait:'Подготавливаю данные для предпросмотра…',snapshot:'Изменения после запуска экспорта попадут в следующий ролик.'},
en:{eyebrow:'YOUR MUSIC. YOUR MOTION.',heading:'Make your sound visible.',intro:'Create a visual world that responds to your music.',source:'01 / Music and images',music:'Choose music',noAudio:'No audio selected',backgroundFile:'Background: image / video',logoFile:'Center image / channel logo',clear:'Remove',mutedBackground:'Background video is always muted.',prepare:'Prepare preview',presets:'02 / Visual presets',scene:'03 / Make it yours',background:'Background',gradient:'Gradient',image:'Image',video:'Video',shape:'Shape',circle:'Circle',triangle:'Triangle',square:'Square',none:'No shape',spectrum:'Spectrum',ring:'Ring',bars:'Bars',wave:'Wave',off:'Off',accent:'Accent',secondColor:'Second color',baseColor:'Base color',particles:'Particles',stars:'Stars',sparks:'Sparks',snow:'Snow',title:'Title',subtitle:'Caption / artist',savePreset:'Save settings',loadPreset:'Restore settings',emptyPreview:'Start with your music',emptyHint:'Add a background and logo, or keep them empty.',exportEyebrow:'YOUR FINISHED VIDEO',export:'Export video',aspect:'Format',resolution:'Quality',fps:'Frame rate',start:'Start, seconds',end:'End, 0 means full track',renderNote:'Final video is rendered separately. You can keep using the rest of the app.',render:'Create MP4',cancel:'Cancel',download:'Download video',previewNote:'Preview adapts to your screen. Selected resolution and FPS apply to the exported video.',particleCount:'Particle count',strength:'Music response',glow:'Glow',rotation:'Rotation',dim:'Background dimming',zoom:'Background motion',chooseAudio:'Choose an audio file first.',changed:'Files changed. Prepare the preview again.',uploading:'Uploading files…',queued:'Queued',analysis:'Analysing music and preparing the background…',ready:'Ready. Play your music and explore the controls.',rendering:'Rendering video',complete:'Video ready. Its export settings were saved separately.',cancelled:'Task cancelled.',failed:'Could not prepare this file. Check the format and try again.',saved:'Settings saved on this device.',loaded:'Settings restored. Load your images and audio separately.',missingPreset:'No saved settings on this device yet.',error:'Could not complete the action.',local:'LOCAL TEST BUILD',featureWait:'Preparing preview data…',snapshot:'Changes after export starts will apply to the next video.'}};
Object.assign(words.ru,{history:'Мои готовые ролики',historyEmpty:'Здесь появятся твои видео. Файлы хранятся временно — сохраняй готовые результаты.',downloadFallback:'Нажми ссылку ещё раз, чтобы скачать через браузер.'});
Object.assign(words.en,{history:'My videos',historyEmpty:'Your videos will appear here. Files are temporary — download the results you want to keep.',downloadFallback:'Tap the link again to download using your browser.'});
Object.assign(words.ru,{styleDownload:'Скачать JSON',styleReady:'Файл настроек готов. Нажми «Скачать JSON».',pendingRestore:'Восстановлен сохранённый черновик. Новые изображения, которые не были обновлены, нужно выбрать заново.'});
Object.assign(words.en,{styleDownload:'Download JSON',styleReady:'Settings file ready. Tap Download JSON.',pendingRestore:'Saved draft restored. Reselect any new images you had not uploaded.'});
Object.assign(words.ru,{composition:'Логотип и спектр',framing:'Кадрирование фона',typography:'Текст и переходы',logoX:'Логотип: по горизонтали',logoY:'Логотип: по вертикали',logoSize:'Размер логотипа',pulse:'Пульсация логотипа',spectrumY:'Высота спектра',spectrumSize:'Размах спектра',panX:'Фон: по горизонтали',panY:'Фон: по вертикали',blur:'Размытие фона',vignette:'Затемнение по краям',fit:'Размещение фона',cover:'Заполнить кадр',contain:'Показать целиком',textY:'Положение текста',textSize:'Размер текста',textColor:'Цвет текста',fadeIn:'Плавное начало, секунды',fadeOut:'Плавное окончание, секунды',undo:'Отменить',redo:'Вернуть',shortPreview:'Видеопроба · 5 секунд',previewReady:'Видеопроба готова. Полный ролик создаётся отдельной кнопкой.',styles:'Мои оформления',styleName:'Название оформления',stylePick:'Выбери оформление',saveStyle:'Сохранить оформление',loadStyle:'Применить',deleteStyle:'Удалить оформление',exportStyle:'Скачать настройки',importStyle:'Загрузить настройки',styleNote:'Настройки оформления не содержат музыку и изображения.',nameRequired:'Укажи название оформления.',restored:'Черновик восстановлен. Можно продолжить.',updateAssets:'Обновить изображения',changedAssets:'Изображения изменились. Обнови их — музыка повторно не анализируется.',draftSaved:'Черновик сохранён',draftUntil:'Файлы доступны до',resetLayout:'Сбросить оформление',sessionExpired:'Файлы черновика уже удалены. Выбери музыку заново.',busy:'Очередь занята. Попробуй немного позже.',tooLarge:'Общий размер файлов слишком большой.',noSpace:'Не хватает места для обработки. Попробуй позже.'});
Object.assign(words.en,{composition:'Logo and spectrum',framing:'Background framing',typography:'Text and transitions',logoX:'Logo horizontal position',logoY:'Logo vertical position',logoSize:'Logo size',pulse:'Logo pulse',spectrumY:'Spectrum vertical position',spectrumSize:'Spectrum amplitude',panX:'Background horizontal position',panY:'Background vertical position',blur:'Background blur',vignette:'Vignette',fit:'Background fit',cover:'Fill frame',contain:'Fit whole image',textY:'Text position',textSize:'Text size',textColor:'Text color',fadeIn:'Fade in, seconds',fadeOut:'Fade out, seconds',undo:'Undo',redo:'Redo',shortPreview:'Video sample · 5 seconds',previewReady:'Video sample ready. Use Create MP4 for the full video.',styles:'My visual styles',styleName:'Style name',stylePick:'Choose a style',saveStyle:'Save style',loadStyle:'Apply',deleteStyle:'Delete style',exportStyle:'Download settings',importStyle:'Import settings',styleNote:'Style settings do not include audio or images.',nameRequired:'Enter a style name.',restored:'Draft restored. Continue editing.',updateAssets:'Update images',changedAssets:'Images changed. Update them without analysing the music again.',draftSaved:'Draft saved',draftUntil:'Files available until',resetLayout:'Reset visual settings',sessionExpired:'Draft files have expired. Choose your audio again.',busy:'The queue is busy. Try again shortly.',tooLarge:'The combined file size is too large.',noSpace:'Not enough processing space. Try again later.'});
let language=new URLSearchParams(location.search).get('lang')||storage.get('swidj-video-language')||'ru';if(!words[language])language='ru';
const t=key=>words[language][key]||key;
const ids=['backgroundKind','shape','spectrum','particles','color','color2','background','title','subtitle','aspect','resolution','fps','fit','textColor',...Object.keys(ranges).filter(key=>key!=='seed')];
const numeric=new Set([...Object.keys(ranges),'resolution','fps']);
const history=new SceneHistory();let dirtyAssets=new Set(),needsAudio=true,restoring=false,preparing=false,lastSaved=0;
let config,scene,draft=null,renderJob=null,pollTimer,revision=0,featureBlock=null,featureRequest=0,featuresBusy=false,lastDraw=0,selectedAudio=null;
const assets={},audio=$('audio'),video=$('video-background'),canvas=$('canvas'),ctx=canvas.getContext('2d');
let historyTimer;
let telegramData='';try{telegramData=window.parent.Telegram?.WebApp?.initData||'';}catch{}
async function api(path,options={}){
 const response=await fetch('api/'+path,{...options,headers:{'X-SwiDJ-Local':'1','X-Telegram-Init-Data':telegramData,...options.headers}});
 if(!response.ok)throw new Error(String(response.status));return response.json();
}
function notice(key){$('notice').textContent=t(key);}
function errorNotice(error){notice(({429:'busy',413:'tooLarge',507:'noSpace',404:'sessionExpired'})[error.message]||'error');}
const profileKey=key=>'swidj-video-'+key+':'+config.profile;
function persist(){
 if(!config||restoring)return;
 const saved=storage.set(profileKey('session'),JSON.stringify({scene,draft:draft?.id||null,position:audio.currentTime||0,pendingAssets:Boolean(dirtyAssets.size)}));
 $('draft-state').textContent=saved&&draft&&!needsAudio&&!dirtyAssets.size?t('draftSaved')+' · '+t('draftUntil')+' '+new Date(draft.expires*1000).toLocaleTimeString(language,{hour:'2-digit',minute:'2-digit'}):'';
}
function historyButtons(){$('undo').disabled=!history.past.length;$('redo').disabled=!history.future.length;}
function commit(key=''){history.capture(scene,key);historyButtons();}
function nativeDownload(event){
 let telegram;try{telegram=window.parent.Telegram?.WebApp;}catch{}
 const link=event.currentTarget;
 if(link.dataset.nativeFailed||typeof telegram?.downloadFile!=='function')return;
 event.preventDefault();
 const extension=(link.download||'').endsWith('.json')?'.json':'.mp4';
 try{telegram.downloadFile({url:link.href,file_name:(link.download||'SwiDJ.mp4').replace(/[\\/:*?"<>|]/g,'').replace(/\.(mp4|json)$/i,'').slice(0,96)+extension},accepted=>{if(!accepted){link.dataset.nativeFailed='1';notice('downloadFallback');}});}
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
function translate(){document.documentElement.lang=language;for(const element of document.querySelectorAll('[data-i18n]'))element.textContent=t(element.dataset.i18n);for(const element of document.querySelectorAll('[data-placeholder]')){element.placeholder=t(element.dataset.placeholder);element.setAttribute('aria-label',t(element.dataset.placeholder));}$('language').textContent=language==='ru'?'EN':'RU';if(config?.dev)$('environment').textContent=t('local');for(const element of document.querySelectorAll('[data-slider]'))element.textContent=t(element.dataset.slider);if($('saved-styles'))listStyles($('saved-styles').value);}
function sync(){for(const id of ids)if($(id))$(id).value=scene[id];for(const output of document.querySelectorAll('[data-output]'))output.textContent=String(scene[output.dataset.output]);for(const button of document.querySelectorAll('[data-preset]'))button.setAttribute('aria-pressed',String(scene.preset===button.dataset.preset));resize();draw();}
function resize(){const ratio=scene.aspect==='portrait'?9/16:scene.aspect==='square'?1:16/9;const width=Math.min(960,Math.max(240,canvas.parentElement.clientWidth));if(canvas.width!==Math.round(width))canvas.width=Math.round(width);if(canvas.height!==Math.round(width/ratio))canvas.height=Math.round(width/ratio);}
function clock(seconds){return `${Math.floor(seconds/60)}:${String(Math.floor(seconds%60)).padStart(2,'0')}`;}
function endTime(){return draft?Math.min(scene.end||draft.duration,draft.duration):0;}
function read(){for(const id of ids){const node=$(id);if(node)scene[id]=numeric.has(id)?Number(node.value):node.value;}for(const output of document.querySelectorAll('[data-output]'))output.textContent=String(scene[output.dataset.output]);resize();draw();persist();}
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
function draw(){if(!scene)return;drawScene(ctx,canvas.width,canvas.height,scene,Math.max(0,audio.currentTime-scene.start),interpolate(audio.currentTime),assets,endTime()-scene.start||Infinity);}
function tick(timestamp){
 if(!audio.paused&&timestamp-lastDraw>1000/30){lastDraw=timestamp;draw();$('seek').value=audio.currentTime;$('clock').textContent=clock(audio.currentTime)+' / '+clock(draft?.duration||0);loadFeatures(audio.currentTime);if(audio.currentTime>=endTime())pause();}
 if(!audio.paused&&timestamp-lastSaved>2000){lastSaved=timestamp;persist();}
 requestAnimationFrame(tick);
}
function pause(){audio.pause();video.pause();$('render-preview')?.pause();$('play').textContent='▶';}
async function play(){
 if(!draft)return;
 if(!audio.paused)return pause();
 if(audio.currentTime<scene.start||audio.currentTime>=endTime())audio.currentTime=scene.start;
 loadFeatures(audio.currentTime);video.muted=true;
 const playing=audio.play();
 if(scene.backgroundKind==='video'&&assets.video){if(Number.isFinite(video.duration)&&video.duration>0)video.currentTime=(audio.currentTime-scene.start)%video.duration;video.play().catch(()=>notice('error'));}
 await playing;$('play').textContent='Ⅱ';
}
function image(url){return new Promise((resolve,reject)=>{const img=new Image();img.onload=()=>resolve(img);img.onerror=reject;img.src=url;});}
async function ready(job,preserve=false){
 draft=job;featureBlock=null;featureRequest++;featuresBusy=false;audio.src=job.files.audio;
 if(job.files['background-image'])assets.background=await image(job.files['background-image']);else delete assets.background;
 if(job.files.logo)assets.logo=await image(job.files.logo);else delete assets.logo;
 if(job.files['background-video']){video.src=job.files['background-video'];video.load();assets.video=video;}else{video.removeAttribute('src');video.load();delete assets.video;}
 if(!preserve||scene.backgroundKind!=='color'&&scene.backgroundKind!==job.backgroundKind)scene.backgroundKind=job.backgroundKind;
 for(const option of $('backgroundKind').options)option.disabled=option.value!=='color'&&option.value!==job.backgroundKind;
 if(scene.start>=job.duration){scene.start=0;scene.end=0;}if(scene.end>job.duration)scene.end=job.duration;
 needsAudio=false;dirtyAssets.clear();$('prepare').disabled=true;sync();await loadFeatures(scene.start);$('empty-preview').hidden=true;
 $('play').disabled=$('seek').disabled=$('restart').disabled=$('render').disabled=$('sample-render').disabled=false;$('seek').max=job.duration;$('clock').textContent='0:00 / '+clock(job.duration);$('prepare').textContent=t('prepare');notice('ready');draw();persist();
}
function fileChanged(name='audio'){revision++;pause();if(name==='audio'){draft=null;needsAudio=true;}else dirtyAssets.add(name);featureBlock=null;featureRequest++;featuresBusy=false;$('play').disabled=$('seek').disabled=$('restart').disabled=$('render').disabled=$('sample-render').disabled=true;$('prepare').disabled=preparing||Boolean(renderJob);$('prepare').textContent=t(draft?'updateAssets':'prepare');notice(draft?'changedAssets':'changed');persist();}
async function prepare(){
 if(preparing||renderJob)return;
 const file=selectedAudio||$('audio-file').files[0];if(!draft&&!file)return notice('chooseAudio');
 const updating=Boolean(draft&&!needsAudio&&dirtyAssets.size);if(draft&&!updating)return;
 pause();const form=new FormData();if(!updating)form.append('audio',file,file.name||'studio-mix.wav');
 for(const name of ['background','logo'])if(!updating||dirtyAssets.has(name)){if($(name+'-file').files[0])form.append(name,$(name+'-file').files[0]);else if(updating)form.append('remove_'+name,'1');}
 const ticket=revision;preparing=true;$('prepare').disabled=true;notice('uploading');
 try{let job=await api(updating?'assets/'+draft.id:'drafts',{method:'POST',body:form});$('cancel').hidden=false;renderJob=job;
  while(['queued','analysis','upload'].includes(job.state)){
   if(ticket!==revision){await api('cancel/'+job.id,{method:'POST'});return;}
   notice(job.state==='queued'?'queued':'analysis');await new Promise(resolve=>setTimeout(resolve,700));job=await api('jobs/'+job.id);renderJob=job;
  }
  if(job.state==='ready'&&ticket===revision)await ready(job);else notice(job.state==='cancelled'?'cancelled':'failed');
 }catch(error){errorNotice(error);}finally{preparing=false;$('prepare').disabled=Boolean(draft&&!needsAudio&&!dirtyAssets.size);$('cancel').hidden=true;renderJob=null;}
}
async function render(short=false){
 if(preparing||renderJob)return;
 if(!draft)return;read();if(!Number.isFinite(scene.start)||!Number.isFinite(scene.end)||scene.start>=draft.duration||scene.end&&scene.end<=scene.start)return notice('error');
 $('render').disabled=$('sample-render').disabled=true;$('prepare').disabled=true;$('download').hidden=true;$('progress').hidden=false;$('cancel').hidden=false;pause();$('render-preview').pause();
 let snapshot={...scene};if(short){const start=Math.max(scene.start,Math.min(audio.currentTime,endTime()-.1));snapshot={...scene,start,end:Math.min(endTime(),start+5),resolution:720,fps:30,title:scene.title.slice(0,100)+' · 5s'};}
 try{
  let job=await api('render/'+draft.id,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(snapshot)});renderJob=job;
  while(['queued','render'].includes(job.state)){
   $('render-status').textContent=(job.state==='queued'?t('queued')+' · '+(job.position||1):t('rendering')+' · '+Math.round((job.progress||0)*100)+'%')+' — '+t('snapshot');
   $('progress').value=job.progress||0;await new Promise(resolve=>setTimeout(resolve,800));job=await api('jobs/'+job.id);renderJob=job;
  }
  if(job.state==='complete'){$('download').href=job.files.result;$('download').download=(job.scene.title||'SwiDJ')+'.mp4';$('download').hidden=false;$('progress').value=1;$('render-status').textContent=t(short?'previewReady':'complete');if(short){$('render-preview').src=job.files.result;$('render-preview').hidden=false;$('render-preview').load();}}
  else $('render-status').textContent=t(job.state==='cancelled'?'cancelled':'failed');
 }catch(error){errorNotice(error);$('render-status').textContent=t('error');}finally{$('render').disabled=$('sample-render').disabled=!draft||needsAudio||Boolean(dirtyAssets.size);$('prepare').disabled=Boolean(draft&&!needsAudio&&!dirtyAssets.size);$('cancel').hidden=true;renderJob=null;refreshHistory();}
}
function savedStyles(){
 try{const values=JSON.parse(storage.get(profileKey('styles'))||'[]');return Array.isArray(values)?values.filter(v=>typeof v?.name==='string'&&v.scene&&typeof v.scene==='object').slice(0,12):[];}catch{return [];}
}
function listStyles(selected=''){
 const select=$('saved-styles');select.replaceChildren();const empty=document.createElement('option');empty.value='';empty.textContent=t('stylePick');select.append(empty);
 for(const style of savedStyles()){const option=document.createElement('option');option.value=style.name;option.textContent=style.name;select.append(option);}select.value=selected;
}
function applyStyle(value){
 commit();scene=normalize({...value,title:scene.title,subtitle:scene.subtitle,start:scene.start,end:scene.end},config.defaults,config.presets);
 if(draft&&scene.backgroundKind!=='color'&&scene.backgroundKind!==draft.backgroundKind)scene.backgroundKind=draft.backgroundKind;
 sync();persist();historyButtons();notice('loaded');
}
function editorTools(){
 $('save-preset').dataset.i18n='saveStyle';$('load-preset').dataset.i18n='loadStyle';
 const groups=[['composition',['logoX','logoY','logoSize','pulse','spectrumY','spectrumSize']],['framing',['panX','panY','blur','vignette']],['typography',['textY','textSize','fadeIn','fadeOut']]];
 for(const [name,keys] of groups.slice().reverse()){
  const details=document.createElement('details');details.className='control-group';const summary=document.createElement('summary');summary.dataset.i18n=name;details.append(summary);
  if(name==='framing')details.insertAdjacentHTML('beforeend','<label><span data-i18n="fit"></span><select id="fit"><option value="cover" data-i18n="cover"></option><option value="contain" data-i18n="contain"></option></select></label>');
  if(name==='typography')details.insertAdjacentHTML('beforeend','<label><span data-i18n="textColor"></span><input type="color" id="textColor"></label>');
  for(const key of keys){const [min,max,step]=ranges[key];const label=document.createElement('label');label.innerHTML=`<span class="slider-label"><span data-slider="${key}"></span><output data-output="${key}"></output></span><input type="range" id="${key}" min="${min}" max="${max}" step="${step}">`;details.append(label);}
  $('sliders').after(details);
 }
 const toolbar=document.createElement('div');toolbar.className='edit-toolbar';toolbar.innerHTML='<button id="undo" type="button" class="quiet" data-i18n="undo" disabled></button><button id="redo" type="button" class="quiet" data-i18n="redo" disabled></button><button id="reset-layout" type="button" class="quiet" data-i18n="resetLayout"></button><span id="draft-state" role="status"></span>';canvas.parentElement.before(toolbar);
 $('undo').onclick=()=>{scene=history.undo(scene);sync();persist();historyButtons();};$('redo').onclick=()=>{scene=history.redo(scene);sync();persist();historyButtons();};
 $('reset-layout').onclick=()=>{commit();scene=presetScene(scene,config.defaults,config.presets.neon,'neon');sync();persist();historyButtons();};
 const sample=document.createElement('button');sample.id='sample-render';sample.type='button';sample.className='button secondary';sample.dataset.i18n='shortPreview';sample.disabled=true;$('render').before(sample);sample.onclick=()=>render(true);
 const clip=document.createElement('video');clip.id='render-preview';clip.controls=true;clip.playsInline=true;clip.hidden=true;clip.preload='metadata';$('render-status').after(clip);
 const styles=document.createElement('div');styles.className='saved-styles';styles.innerHTML='<h3 data-i18n="styles"></h3><input id="style-name" type="text" maxlength="40" data-placeholder="styleName"><select id="saved-styles"></select><p class="note" data-i18n="styleNote"></p>';$('save-preset').parentElement.before(styles);
 const actions=document.createElement('div');actions.className='style-actions';actions.innerHTML='<button id="delete-style" type="button" class="quiet" data-i18n="deleteStyle"></button><button id="export-style" type="button" class="quiet" data-i18n="exportStyle"></button><label class="quiet file-label"><span data-i18n="importStyle"></span><input id="import-style" type="file" accept="application/json,.json"></label>';$('save-preset').parentElement.after(actions);
 $('save-preset').onclick=()=>{read();const name=$('style-name').value.trim().slice(0,40);if(!name)return notice('nameRequired');const values=savedStyles().filter(v=>v.name!==name);values.unshift({name,scene:{...scene}});storage.set(profileKey('styles'),JSON.stringify(values.slice(0,12)));listStyles(name);notice('saved');};
 $('load-preset').onclick=()=>{const value=savedStyles().find(v=>v.name===$('saved-styles').value);if(!value)return notice('missingPreset');applyStyle(value.scene);};
 $('saved-styles').onchange=()=>{$('style-name').value=$('saved-styles').value;};
 $('delete-style').onclick=()=>{storage.set(profileKey('styles'),JSON.stringify(savedStyles().filter(v=>v.name!==$('saved-styles').value)));listStyles();};
 const settingsLink=document.createElement('a');settingsLink.className='button secondary';settingsLink.id='settings-download';settingsLink.hidden=true;settingsLink.dataset.i18n='styleDownload';settingsLink.download='SwiDJ-style.json';settingsLink.onclick=nativeDownload;actions.after(settingsLink);
 $('export-style').onclick=async()=>{read();$('export-style').disabled=true;settingsLink.hidden=true;try{const result=await api('settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(scene)});settingsLink.href=result.files.settings;settingsLink.hidden=false;notice('styleReady');}catch(error){errorNotice(error);}finally{$('export-style').disabled=false;}};
 $('import-style').onchange=async()=>{try{const file=$('import-style').files[0];if(!file||file.size>32768)throw Error();const value=JSON.parse(await file.text());if(value.type!=='swidj-visual-style'||value.version!==1||!value.scene||typeof value.scene!=='object')throw Error();applyStyle(value.scene);}catch{notice('error');}finally{$('import-style').value='';}};
 const old=storage.get('swidj-video-preset:'+config.profile);if(!savedStyles().length&&old){try{storage.set(profileKey('styles'),JSON.stringify([{name:'My style',scene:normalize(JSON.parse(old),config.defaults,config.presets)}]));}catch{}}
 listStyles();
 document.addEventListener('keydown',event=>{if(!(event.ctrlKey||event.metaKey)||event.key.toLowerCase()!=='z'||document.activeElement?.matches('input[type=text],textarea,select'))return;event.preventDefault();(event.shiftKey?$('redo'):$('undo')).click();});
}
async function restoreSession(){
 if(new URLSearchParams(location.search).get('new')==='1')return;
 try{const saved=JSON.parse(storage.get(profileKey('session'))||'null');if(!saved)return;restoring=true;scene=normalize(saved.scene,config.defaults,config.presets);sync();
  if(saved.draft){const job=await api('jobs/'+saved.draft);if(job.kind==='draft'&&job.state==='ready'){await ready(job,true);audio.currentTime=Math.max(scene.start,Math.min(Number(saved.position)||0,endTime()));await loadFeatures(audio.currentTime);draw();notice(saved.pendingAssets?'pendingRestore':'restored');}}
 }catch(error){if(error.message==='404')notice('sessionExpired');}finally{restoring=false;persist();}
}
async function init(){
 config=await api('config');scene={...config.defaults};
 const controls=[['strength',0,3,.05],['glow',0,1,.05],['particleCount',0,200,1],['rotation',-1,1,.05],['dim',0,.95,.05],['zoom',1,1.5,.01]];
 for(const [key,min,max,step] of controls){const label=document.createElement('label');const line=document.createElement('span');line.className='slider-label';const text=document.createElement('span');text.dataset.slider=key;const output=document.createElement('output');output.dataset.output=key;line.append(text,output);const input=document.createElement('input');Object.assign(input,{type:'range',id:key,min,max,step});label.append(line,input);$('sliders').append(label);}
 editorTools();
 const names={neon:'Neon Orbit',prism:'Prism',stars:'Starfield',minimal:'Minimal',retro:'Retro',liquid:'Liquid',stage:'Stage',photo:'Photo Motion'};
 for(const [key,value] of Object.entries(config.presets)){const button=document.createElement('button');button.type='button';button.className='preset';button.dataset.preset=key;button.textContent=names[key];button.style.setProperty('--a',value.color||'#334b57');button.style.setProperty('--b',value.color2||'#121b2c');button.onclick=()=>{commit();scene=presetScene(scene,config.defaults,value,key);sync();persist();};$('presets').append(button);}
 const history=document.createElement('details');history.className='panel history-panel';const summary=document.createElement('summary');summary.dataset.i18n='history';summary.textContent=t('history');const historyList=document.createElement('div');historyList.id='history-list';history.append(summary,historyList);document.querySelector('.footer-note').before(history);history.ontoggle=()=>{if(history.open)refreshHistory();};
 translate();sync();requestAnimationFrame(tick);refreshHistory();$('download').onclick=nativeDownload;
 for(const id of ids)$(id).addEventListener('input',()=>{commit(id);read();});
 $('language').onclick=()=>{language=language==='ru'?'en':'ru';storage.set('swidj-video-language',language);translate();refreshHistory();};
 $('audio-file').onchange=()=>{selectedAudio=$('audio-file').files[0]||null;$('audio-name').textContent=selectedAudio?.name||t('noAudio');if(selectedAudio&&!scene.title){scene.title=selectedAudio.name.replace(/\.[^.]+$/,'').slice(0,120);sync();}fileChanged();};
 for(const name of ['background','logo']){$(name+'-file').onchange=()=>fileChanged(name);$('remove-'+name).onclick=()=>{$(name+'-file').value='';fileChanged(name);};}
 $('prepare').onclick=prepare;$('render').onclick=()=>render(false);$('play').onclick=()=>play().catch(()=>notice('error'));
 $('restart').onclick=()=>{audio.currentTime=scene.start;loadFeatures(scene.start).then(draw);if(assets.video)video.currentTime=0;};
 $('seek').oninput=()=>{audio.currentTime=Number($('seek').value);if(assets.video&&video.duration)video.currentTime=Math.max(0,audio.currentTime-scene.start)%video.duration;loadFeatures(audio.currentTime).then(draw);$('clock').textContent=clock(audio.currentTime)+' / '+clock(draft.duration);};
 $('cancel').onclick=async()=>{if(renderJob)try{await api('cancel/'+renderJob.id,{method:'POST'});}catch{notice('error');}};
 window.addEventListener('resize',()=>{resize();draw();});document.addEventListener('visibilitychange',()=>{if(document.hidden)pause();});audio.onended=pause;audio.onpause=()=>persist();
 window.addEventListener('message',event=>{if(event.origin!==location.origin||event.source!==window.parent||event.data?.type!=='swidj:music-video'||!(event.data.audio instanceof Blob))return;selectedAudio=event.data.audio;$('audio-name').textContent=event.data.title||'Studio mix';scene.title=(event.data.title||scene.title).slice(0,120);if(words[event.data.language]){language=event.data.language;translate();}fileChanged();sync();});
 await restoreSession();
 if(window.parent!==window)window.parent.postMessage({type:'swidj:music-video-ready'},location.origin);
}
init().catch(()=>notice('error'));
