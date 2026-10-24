import {AudioEngine, stamp} from './audio.js';

const paths = {
  home:'M3 10 12 3l9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1Z',
  search:'M21 21l-5-5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0',
  library:'M4 4v16M9 4v16M14 4v16M18 4l3 16',
  studio:'M5 3v5m0 4v9M12 3v10m0 4v4M19 3v3m0 4v11M2 8h6m1 9h6m1-11h6',
  play:'m9 5 11 7-11 7Z', pause:'M8 5v14M16 5v14', next:'m5 5 10 7-10 7ZM19 5v14',
  previous:'m19 5-10 7 10 7ZM5 5v14', heart:'M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z',
  arrow:'M4 12h16m-6-6 6 6-6 6', plus:'M12 5v14M5 12h14', more:'M5 12h.01M12 12h.01M19 12h.01',
  download:'M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5', upload:'M12 16V4m-5 5 5-5 5 5M4 16v5h16v-5',
  volume:'m11 5-6 4H2v6h3l6 4ZM15 8a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14',
  repeat:'m17 2 4 4-4 4M3 11V8a2 2 0 0 1 2-2h16M7 22l-4-4 4-4m14-1v3a2 2 0 0 1-2 2H3',
  info:'M12 11v6m0-10v.01M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0',
  trash:'M3 6h18M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7',
  folder:'M3 7V4h6l3 3h9v13H3Z', send:'m3 3 19 9-19 9 4-9Zm4 9h15', music:'M9 18V5l12-3v13M9 8l12-3M9 18a3 3 0 1 1-6-1 3 3 0 0 1 6 1M21 15a3 3 0 1 1-6-1 3 3 0 0 1 6 1'
};
const icon = name => `<svg viewBox="0 0 24 24" aria-hidden="true" class="${name}"><path d="${paths[name] || paths.music}"/></svg>`;
const e = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const $ = id => document.getElementById(id);
const copy = {
  ru:{home:'Главная',search:'Поиск',library:'Моя музыка',studio:'Студия',yourSpace:'ТВОЁ ПРОСТРАНСТВО',makeItYours:'Звучит по-твоему.',railNote:'Чуть больше баса. Совсем другое настроение.',openStudio:'Открыть студию →',musicSpace:'Твоё музыкальное пространство',footer:'Слушай. Создавай. Сохраняй.',demo:'Демо',connected:'В Telegram',heroLabel:'МУЗЫКА БЕЗ ЛИШНИХ ДВИЖЕНИЙ',hero1:'Твоя музыка.',hero2:'Твои правила.',heroNote:'Любимые треки, личные плейлисты и свой звук — в одном месте.',findMusic:'Найти музыку',yourSound:'ТВОЙ ЗВУК — ТВОЙ ВЫБОР',continue:'Включи настроение',continueNote:'Нажми на обложку — и слушай',allMusic:'Вся музыка →',fresh:'Твоя библиотека',freshNote:'Продолжи с того, что сохранил',quickStudio:'Сделай свой микс',quickStudioNote:'Скорость, бас и короткий пример',quickLibrary:'Всё любимое рядом',quickLibraryNote:'Собери плейлист под своё настроение',searchTitle:'Найди свой следующий трек.',searchNote:'Введи название или исполнителя.',searchPlaceholder:'Название песни или исполнитель',searchButton:'Найти',searchEmpty:'Что включим?',searchHint:'Ищи музыку по названию или открой сохранённые треки.',results:'Результаты',searching:'Ищу записи…',noResults:'Ничего не найдено',retrySearch:'Попробуй другое название или добавь исполнителя.',demoSearch:'В деморежиме поиск работает по шести оригинальным инструментальным примерам.',libraryTitle:'Всё твоё. В одном месте.',libraryNote:'Треки, которые хочется оставить.',all:'Все треки',favorites:'Избранное',uploads:'Мои файлы',playlists:'Плейлисты',newPlaylist:'Новый плейлист',playlistName:'Название плейлиста',create:'Создать',cancel:'Отмена',tracks:'треков',emptyLibrary:'Здесь будет твоя музыка',emptyLibraryNote:'Сохрани трек из поиска или добавь свой файл через бота.',emptyPlaylist:'Добавь музыку в плейлист',emptyPlaylistNote:'Открой меню трека и выбери «В плейлист».',addPlaylist:'В плейлист',save:'В избранное',unsave:'Убрать из избранного',remove:'Убрать из библиотеки',removeQuestion:'Убрать трек из избранного и всех плейлистов?',removed:'Трек убран из библиотеки',saved:'Сохранено',created:'Плейлист создан',studioTitle:'Твой трек. Новый характер.',studioNote:'Выбери аудио, настрой звук и послушай результат.',localProcessing:'Обработка на твоём устройстве',chooseFile:'Открыть свой файл',chooseFirst:'Выбери трек или свой аудиофайл',chooseFirstNote:'Аудио остаётся на твоём устройстве.',soundSettings:'Настрой свой звук',soundNote:'Изменения слышны во время воспроизведения.',bass:'Бас',bassLess:'Меньше',bassOff:'Оригинал',bassGentle:'Мягкий',bassMedium:'Средний',bassStrong:'Сильный',speed:'Скорость и тон',slower:'Медленнее',original:'Оригинал',faster:'Быстрее',preview:'Пример · 15 сек',export:'Сохранить микс · WAV',reset:'Сбросить настройки',rendering:'Готовлю аудио…',studioFine:'Скорость меняется вместе с тоном. Экспорт в браузере — до 3 минут. Для длинного трека и MP3 используй студию в боте.',demoNote:'Демо: оригинальные инструментальные примеры. Изменения библиотеки сохраняются только в этом браузере.',demoStudio:'Файл обрабатывается локально, без загрузки на сервер.',selectTrack:'Выбери трек',ready:'Твой следующий любимый звук',play:'Слушать',pause:'Пауза',previous:'Предыдущий трек',next:'Следующий трек',favorite:'В избранное',more:'Действия с треком',sent:'Варианты отправлены в чат бота',send:'Получить в боте',sendNote:'Эта запись пока не загружена. Открой чат бота, чтобы выбрать и скачать полную версию.',openChat:'Открыть чат бота',demoSend:'В деморежиме отправка в Telegram недоступна.',fileTooLarge:'Выбери аудиофайл до 20 МБ.',invalidAudio:'Не удалось открыть аудио. Попробуй MP3, WAV или OGG.',long:'Экспорт в браузере — до 3 минут. Для полного длинного трека используй бота.',error:'Не получилось. Попробуй ещё раз.',expired:'Открой приложение заново из Telegram — вход устарел.',unavailable:'Раздел временно недоступен.',rateLimit:'Подожди несколько секунд и попробуй снова.',previewReady:'Пример готов',exportReady:'Микс сохранён',localSave:'Для постоянного сохранения отправь этот файл боту.',back:'Назад',loading:'Загружаю твою музыку…',authError:'Не удалось подтвердить вход',authHint:'Открой приложение из личного чата с ботом.',repeat:'Повтор трека',seek:'Позиция в треке',volume:'Громкость',language:'Сменить язык',capacity:'Достигнут лимит библиотеки или плейлиста.'},
  en:{home:'Home',search:'Search',library:'Your music',studio:'Studio',yourSpace:'YOUR SPACE',makeItYours:'Make it sound like you.',railNote:'A little more bass. A whole new mood.',openStudio:'Open studio →',musicSpace:'Your personal music space',footer:'Listen. Create. Keep.',demo:'Demo',connected:'In Telegram',heroLabel:'LESS TAPPING. MORE MUSIC.',hero1:'Your music.',hero2:'Your rules.',heroNote:'Favorite tracks, personal playlists and your own sound. All in one place.',findMusic:'Find your music',yourSound:'YOUR SOUND. YOUR CHOICE.',continue:'Find your frequency',continueNote:'Pick a cover. Press play.',allMusic:'All your music →',fresh:'From your collection',freshNote:'Pick up where you left off',quickStudio:'Make it your mix',quickStudioNote:'Speed, bass and a quick preview',quickLibrary:'Keep the good stuff',quickLibraryNote:'Build a playlist for your mood',searchTitle:'Find your next favorite.',searchNote:'Search by song or artist.',searchPlaceholder:'Song title or artist',searchButton:'Search',searchEmpty:'What are we playing?',searchHint:'Find a song or explore your saved music.',results:'Results',searching:'Finding recordings…',noResults:'No tracks found',retrySearch:'Try another title or add the artist.',demoSearch:'Demo search covers six original instrumental samples.',libraryTitle:'All yours. All here.',libraryNote:'For the tracks worth keeping.',all:'All tracks',favorites:'Favorites',uploads:'Your files',playlists:'Playlists',newPlaylist:'New playlist',playlistName:'Playlist name',create:'Create',cancel:'Cancel',tracks:'tracks',emptyLibrary:'Your music starts here',emptyLibraryNote:'Save a search result or send your own file to the bot.',emptyPlaylist:'Make this playlist yours',emptyPlaylistNote:'Open a track menu and choose “Add to playlist”.',addPlaylist:'Add to playlist',save:'Add to favorites',unsave:'Remove from favorites',remove:'Remove from library',removeQuestion:'Remove this track from favorites and all playlists?',removed:'Removed from library',saved:'Saved',created:'Playlist created',studioTitle:'Same track. New energy.',studioNote:'Choose audio, shape the sound and hear the difference.',localProcessing:'Processed on your device',chooseFile:'Open your audio',chooseFirst:'Choose a track or your audio file',chooseFirstNote:'Your file stays on your device.',soundSettings:'Find your sound',soundNote:'Hear your changes while the track plays.',bass:'Bass',bassLess:'Less',bassOff:'Original',bassGentle:'Gentle',bassMedium:'Medium',bassStrong:'Strong',speed:'Speed & pitch',slower:'Slower',original:'Original',faster:'Faster',preview:'Preview · 15 sec',export:'Save mix · WAV',reset:'Reset settings',rendering:'Preparing audio…',studioFine:'Speed changes pitch too. Browser export supports up to 3 minutes. Use the bot studio for longer tracks and MP3.',demoNote:'Demo: original instrumental samples. Library changes stay in this browser.',demoStudio:'Your file is processed locally without a server upload.',selectTrack:'Choose a track',ready:'Your next favorite sound',play:'Play',pause:'Pause',previous:'Previous track',next:'Next track',favorite:'Favorite',more:'Track actions',sent:'Recording choices sent to the bot',send:'Get it in the bot',sendNote:'This recording is not downloaded yet. Open the bot chat to choose and download the full version.',openChat:'Open bot chat',demoSend:'Sending to Telegram is unavailable in demo mode.',fileTooLarge:'Choose an audio file up to 20 MB.',invalidAudio:'Could not open the audio. Try MP3, WAV or OGG.',long:'Browser export supports up to 3 minutes. Use the bot for longer full tracks.',error:'Something went wrong. Please try again.',expired:'Reopen the app from Telegram — your login has expired.',unavailable:'Temporarily unavailable.',rateLimit:'Wait a few seconds and try again.',previewReady:'Preview ready',exportReady:'Mix saved',localSave:'Send this file to the bot to save it permanently.',back:'Back',loading:'Loading your music…',authError:'Could not verify your login',authHint:'Open the app from your private chat with the bot.',repeat:'Repeat track',seek:'Track position',volume:'Volume',language:'Change language',capacity:'Library or playlist limit reached.'}
};
const tg = window.Telegram?.WebApp;
const initData = tg?.initData || '';
const demo = !initData;
let language = 'ru';
try { language = localStorage.getItem('swidj-language') || tg?.initDataUnsafe?.user?.language_code?.slice(0,2) || 'ru'; } catch {}
if (!copy[language]) language = 'en';
const t = key => copy[language][key] || copy.en[key] || key;
const demos = [
  ['Velvet hours','SwiDJ Originals'],['Sunset circuit','SwiDJ Originals'],['After the rain','SwiDJ Originals'],
  ['Blue distance','SwiDJ Originals'],['Soft focus','SwiDJ Originals'],['Golden hour','SwiDJ Originals']
].map(([title,artist], i) => ({id:`demo:${i}`,title,artist,duration:24,kind:'track',playable:true,demo:i}));
let state = {tracks:[],favorites:[],playlists:[],bot:''};
let route = 'home', filter = 'all', playlist = null, current = null, results = null, searching = false, failed = false;
let trackBlob = null, trackUrl = null, previewUrl = null, loadingTrack = 0, toastTimer;
const localTracks = new Map();
const audio = $('audio'), engine = new AudioEngine(audio);
audio.volume = .8;
let demoState;
try { demoState = JSON.parse(localStorage.getItem('swidj-demo-library') || 'null'); } catch {}
const api = async (path, payload) => {
  const response = await fetch('/api/' + path, {method:payload ? 'POST':'GET', headers:{'X-Telegram-Init-Data':initData,...(payload ? {'Content-Type':'application/json'}:{})},body:payload ? JSON.stringify(payload):undefined, credentials:'omit'});
  if (!response.ok) throw new Error(({401:'expired',403:'unavailable',409:'capacity',429:'rateLimit',503:'unavailable'})[response.status] || 'error');
  return response;
};
function toast(key) { $('toast').textContent = t(key); $('toast').classList.add('show'); clearTimeout(toastTimer); toastTimer = setTimeout(()=>$('toast').classList.remove('show'),4500); }
function report(error) { toast(copy.en[error?.message] ? error.message : 'error'); }
function liked(track) { return state.favorites.includes(track.id); }
function trackById(id) { return [...state.tracks,...(state.recent || []),...(results || []),...localTracks.values()].find(s=>s.id===id); }
function color(track) { return track.demo ?? [...track.id].reduce((n,c)=>n+c.charCodeAt(0),0)%6; }
function art(track, small=false) {
  const index = color(track);
  return small ? `<span class="mini-art art-${index}" aria-hidden="true">♪</span>` : `<span class="art art-${index}"><span class="art-corner">${e(track.artist || 'SwiDJ')}</span><span class="art-symbol" aria-hidden="true">${['◒','◓','∿','◌','◍','≋'][index]}</span><span class="card-play">${icon('play')}</span></span>`;
}
function card(track) { return `<article class="music-card"><button class="art-button" data-track="${e(track.id)}" data-action="play" aria-label="${e(t('play')+' '+track.title)}">${art(track)}</button><span class="card-title">${e(track.title)}</span><div class="card-meta"><span class="card-artist">${e(track.artist)}</span><button class="icon-btn" data-track="${e(track.id)}" data-action="like" aria-label="${e(t('favorite'))}" aria-pressed="${liked(track)}">${icon('heart')}</button></div></article>`; }
function row(track) { return `<article class="track-row ${current?.id===track.id?'current':''}"><button class="icon-btn" data-track="${e(track.id)}" data-action="play" aria-label="${e(t('play'))}">${art(track,true)}</button><button class="track-copy plain" data-track="${e(track.id)}" data-action="play"><strong>${e(track.title)}</strong><small>${e(track.artist)}</small></button><span class="track-time">${stamp(track.duration)}</span><button class="icon-btn" data-track="${e(track.id)}" data-action="like" aria-label="${e(t('favorite'))}" aria-pressed="${liked(track)}">${icon('heart')}</button><button class="icon-btn" data-track="${e(track.id)}" data-action="menu" aria-label="${e(t('more'))}">${icon('more')}</button></article>`; }
function empty(title, note, name='music') { return `<div class="empty">${icon(name)}<strong>${e(t(title))}</strong><p>${e(t(note))}</p></div>`; }
function heading(title, note) { return `<div class="page-heading"><p class="eyebrow">${e(t(route))}</p><h1>${e(t(title))}</h1><p>${e(t(note))}</p></div>`; }
function note() { return demo ? `<p class="demo-note">${icon('info')}${e(t('demoNote'))}</p>` : ''; }
function home() {
  const tracks = [...new Map([...(state.recent || []),...state.tracks].map(s=>[s.id,s])).values()].slice(0,4);
  return `<section class="hero"><div class="hero-copy"><p class="eyebrow">${e(t('heroLabel'))}</p><h1>${e(t('hero1'))}<br><em>${e(t('hero2'))}</em></h1><p>${e(t('heroNote'))}</p><button class="btn" data-go="search">${icon('search')}${e(t('findMusic'))}</button></div><div class="hero-disc" aria-hidden="true"></div><span class="hero-tag"><i></i>${e(t('yourSound'))}</span></section><div class="section-head"><div><h2>${e(t(demo?'continue':'fresh'))}</h2><p>${e(t(demo?'continueNote':'freshNote'))}</p></div><button class="text-btn" data-go="library">${e(t('allMusic'))}</button></div>${tracks.length?`<div class="card-grid">${tracks.map(card).join('')}</div>`:empty('emptyLibrary','emptyLibraryNote')}<div class="quick-grid"><button class="quick-card" data-go="studio"><span class="quick-icon">${icon('studio')}</span><span><strong>${e(t('quickStudio'))}</strong><small>${e(t('quickStudioNote'))}</small></span>${icon('arrow').replace('<svg','<svg class="arrow"')}</button><button class="quick-card" data-go="library"><span class="quick-icon">${icon('library')}</span><span><strong>${e(t('quickLibrary'))}</strong><small>${e(t('quickLibraryNote'))}</small></span>${icon('arrow').replace('<svg','<svg class="arrow"')}</button></div>${note()}`;
}
function searchScreen() {
  return heading('searchTitle','searchNote')+`<form id="search-form" class="search-form">${icon('search')}<input id="search-input" type="search" maxlength="120" minlength="2" placeholder="${e(t('searchPlaceholder'))}" aria-label="${e(t('searchPlaceholder'))}" required><button class="btn" ${searching?'disabled':''}>${e(t('searchButton'))}</button></form>${demo?`<p class="demo-note">${icon('info')}${e(t('demoSearch'))}</p>`:''}<div class="section-head"><h2>${e(t('results'))}</h2></div>${searching?`<div class="loading" role="status">${e(t('searching'))}</div>`:results===null?empty('searchEmpty','searchHint','search'):results.length?`<div class="track-list">${results.map(row).join('')}</div>`:empty('noResults','retrySearch','search')}`;
}
function libraryScreen() {
  const selected = state.playlists.find(p=>p.id===playlist);
  let tracks = state.tracks;
  if (selected) tracks = tracks.filter(s=>selected.tracks.includes(s.id));
  else if (filter==='favorites') tracks=tracks.filter(liked);
  else if (filter==='uploads') tracks=tracks.filter(s=>s.kind==='upload');
  const chips = ['all','favorites','uploads','playlists'].map(key=>
    `<button class="chip ${filter===key&&!selected?'active':''}" data-filter="${key}">${e(t(key))}</button>`).join('');
  let body;
  if (filter === 'playlists' && !selected) {
    const folders = state.playlists.map(p=>
      `<button class="playlist-card" data-playlist="${e(p.id)}">${icon('folder')}<span><strong>${e(p.name)}</strong><small>${p.tracks.length} ${e(t('tracks'))}</small></span></button>`).join('');
    body = `<div class="section-head"><h2>${e(t('playlists'))}</h2><button class="text-btn" id="new-playlist">+ ${e(t('newPlaylist'))}</button></div><div class="playlist-grid">${folders}</div>`;
    if (!state.playlists.length) body += empty('emptyPlaylist','emptyPlaylistNote','folder');
  } else {
    const action = selected
      ? `<button class="text-btn" id="back-playlists">${e(t('back'))}</button>`
      : `<button class="text-btn" id="new-playlist">+ ${e(t('newPlaylist'))}</button>`;
    body = `<div class="section-head"><h2>${e(selected?.name || t(filter))} <span class="count">${tracks.length}</span></h2>${action}</div>`;
    body += tracks.length
      ? `<div class="track-list">${tracks.map(row).join('')}</div>`
      : empty(selected?'emptyPlaylist':'emptyLibrary',selected?'emptyPlaylistNote':'emptyLibraryNote');
  }
  return heading('libraryTitle','libraryNote') + `<div class="chips">${chips}</div>` + body + note();
}

const bassOptions = [[-6,'bassLess'],[0,'bassOff'],[3,'bassGentle'],[6,'bassMedium'],[9,'bassStrong']];
function studio() {
  return heading('studioTitle','studioNote')+`<div class="studio-layout"><section class="studio-source">${current?art(current):`<div class="art art-0"><span class="art-symbol">∿</span></div>`}<h2>${e(current?.title || t('chooseFirst'))}</h2><p>${e(current?.artist || t('chooseFirstNote'))}</p><label class="btn secondary" for="local-file">${icon('upload')}${e(t('chooseFile'))}</label><input id="local-file" type="file" accept="audio/*,.mp3,.wav,.ogg,.m4a,.flac"></section><section class="studio-controls"><span class="studio-badge">${e(t('localProcessing'))}</span><h2>${e(t('soundSettings'))}</h2><p>${e(t('soundNote'))}</p><div class="control-label"><label>${e(t('bass'))}</label><output id="bass-value">${engine.bass>0?'+':''}${engine.bass} dB</output></div><div class="bass-options">${bassOptions.map(([value,label])=>`<button class="chip ${value===engine.bass?'active':''}" data-bass="${value}" aria-pressed="${value===engine.bass}">${e(t(label))}</button>`).join('')}</div><div class="control-label"><label for="speed">${e(t('speed'))}</label><output id="speed-value">${engine.speed.toFixed(2)}×</output></div><input id="speed" class="control-range" type="range" min="0.75" max="1.25" step="0.05" value="${engine.speed}"><div class="range-labels"><span>${e(t('slower'))}</span><span>${e(t('original'))}</span><span>${e(t('faster'))}</span></div><button class="btn secondary" id="preview-mix" ${!trackBlob?'disabled':''}>${icon('play')}${e(t('preview'))}</button><button class="btn lime" id="export-mix" ${!trackBlob?'disabled':''}>${icon('download')}${e(t('export'))}</button><button class="text-btn reset-btn" id="reset-fx">${e(t('reset'))}</button><p class="fineprint">${e(t('studioFine'))}</p></section></div><p class="demo-note">${icon('info')}${e(t('demoStudio'))}</p>`;
}
function render() {
  document.documentElement.lang = language;
  document.querySelectorAll('[data-i18n]').forEach(node=>node.textContent=t(node.dataset.i18n));
  const nav = ['home','search','library','studio'].map(key=>`<button class="${route===key?'active':''}" data-go="${key}" ${route===key?'aria-current="page"':''}>${icon(key)}<span>${e(t(key))}</span></button>`).join('');
  $('desktop-nav').innerHTML=nav; $('mobile-nav').innerHTML=nav;
  $('connection').textContent=t(demo?'demo':'connected'); $('language').textContent=language==='ru'?'EN':'RU';
  $('content').innerHTML=failed?empty('authError','authHint','info'):({home,search:searchScreen,library:libraryScreen,studio}[route])();
  $('previous').innerHTML=icon('previous'); $('next').innerHTML=icon('next'); $('repeat').innerHTML=icon('repeat');
  $('volume-icon').innerHTML=icon('volume'); $('expand-studio').innerHTML=icon('studio');
  for (const [id,key] of [['previous','previous'],['next','next'],['repeat','repeat'],['seek','seek'],['volume','volume'],['language','language'],['player-art','openStudio'],['expand-studio','openStudio'],['player-like','favorite']]) $(id).setAttribute('aria-label',t(key));
  updatePlayer();
}
function updatePlayer() {
  $('now-title').textContent=current?.title || t('selectTrack'); $('now-artist').textContent=current?.artist || t('ready');
  $('player-art').className=`mini-art art-${current?color(current):0}`;
  $('player-like').innerHTML=icon('heart'); $('player-like').setAttribute('aria-pressed',String(current?liked(current):false));
  $('play').innerHTML=icon(audio.paused?'play':'pause'); $('play').setAttribute('aria-label',t(audio.paused?'play':'pause'));
}
function navigate(value) {
  route=['home','search','library','studio'].includes(value)?value:'home';
  if (location.hash !== '#'+route) location.hash=route; else render();
}
window.addEventListener('hashchange',()=>{route=location.hash.slice(1);if(!['home','search','library','studio'].includes(route))route='home';render();window.scrollTo(0,0);});

async function mutate(payload) {
  if (!demo) state=await (await api('library',payload)).json();
  else {
    if(payload.action==='favorite') {
      state.favorites=state.favorites.filter(id=>id!==payload.track);
      if(payload.value)state.favorites.push(payload.track);
    } else if(payload.action==='create')state.playlists.push({id:crypto.randomUUID(),name:payload.name,tracks:[]});
    else if(payload.action==='playlist') {
      const p=state.playlists.find(p=>p.id===payload.playlist);
      const track=trackById(payload.track);
      if(track&&!state.tracks.some(s=>s.id===track.id))state.tracks.push(track);
      if(p&&!p.tracks.includes(payload.track))p.tracks.push(payload.track);
    }
    else if(payload.action==='remove') {state.favorites=state.favorites.filter(id=>id!==payload.track);state.playlists.forEach(p=>p.tracks=p.tracks.filter(id=>id!==payload.track));state.tracks=state.tracks.filter(s=>s.id!==payload.track);}
    try {localStorage.setItem('swidj-demo-library',JSON.stringify(state));}catch{}
  }
  render();
}
async function favorite(track) {
  if(track.local)return toast('localSave');
  if(!state.tracks.some(s=>s.id===track.id))state.tracks.push(track);
  await mutate({action:'favorite',track:track.id,value:!liked(track)});
}
function dialog(title, body, actions='') { $('dialog-title').textContent=title;$('dialog-body').innerHTML=body;$('dialog-actions').innerHTML=actions;if(!$('dialog').open)$('dialog').showModal(); }
function newPlaylist() {
  dialog(t('newPlaylist'),`<input id="playlist-name" type="text" maxlength="40" placeholder="${e(t('playlistName'))}" aria-label="${e(t('playlistName'))}" required autocomplete="off">`,`<button class="btn secondary" value="cancel">${e(t('cancel'))}</button><button class="btn" value="create">${e(t('create'))}</button>`);
  $('dialog-form').onsubmit=async event=>{
    if(event.submitter?.value!=='create')return;
    event.preventDefault();const name=$('playlist-name').value.trim();if(!name)return;
    try{await mutate({action:'create',name});$('dialog').close();toast('created');}catch(error){report(error);}
  };
}
function trackMenu(track) {
  $('dialog-form').onsubmit=null;
  dialog(track.title,`<button type="button" class="dialog-option" data-track="${e(track.id)}" data-action="like">${icon('heart')}${e(t(liked(track)?'unsave':'save'))}</button><button type="button" class="dialog-option" data-track="${e(track.id)}" data-action="playlist">${icon('plus')}${e(t('addPlaylist'))}</button><button type="button" class="dialog-option" data-track="${e(track.id)}" data-action="studio">${icon('studio')}${e(t('openStudio'))}</button><button type="button" class="dialog-option" data-track="${e(track.id)}" data-action="send">${icon('send')}${e(t('send'))}</button><button type="button" class="dialog-option" data-track="${e(track.id)}" data-action="remove">${icon('trash')}${e(t('remove'))}</button>`);
}
function choosePlaylist(track) {
  dialog(t('addPlaylist'),state.playlists.map(p=>`<button type="button" class="dialog-option" data-add-playlist="${e(p.id)}" data-track="${e(track.id)}">${icon('folder')}${e(p.name)}</button>`).join('')+`<button type="button" class="dialog-option" id="new-playlist">${icon('plus')}${e(t('newPlaylist'))}</button>`);
}
async function playTrack(track) {
  if (!track.playable && !track.local) {
    dialog(track.title,`<p class="dialog-copy">${e(t('sendNote'))}</p>`,`<button type="button" class="btn" data-track="${e(track.id)}" data-action="send">${icon('send')}${e(t('send'))}</button>`);
    return false;
  }
  const ticket=++loadingTrack;
  await engine.unlock();
  let blob;
  if(track.local)blob=localTracks.get(track.id)?.blob;
  else if(demo) {const response=await fetch(`/demo/${track.demo}.wav`);if(!response.ok)throw new Error('invalidAudio');blob=await response.blob();}
  else blob=await (await api('audio/'+encodeURIComponent(track.id))).blob();
  if(ticket!==loadingTrack)return false;
  audio.pause();if(trackUrl)URL.revokeObjectURL(trackUrl);if(previewUrl){URL.revokeObjectURL(previewUrl);previewUrl=null;}
  trackBlob=blob;trackUrl=URL.createObjectURL(blob);audio.src=trackUrl;current=track;
  engine.setSpeed(engine.speed);await audio.play();updatePlayer();if(route==='studio')render();return true;
}
async function togglePlay() {
  if(!audio.src) {const track=state.tracks.find(s=>s.playable);if(track)return playTrack(track);return navigate('search');}
  await engine.unlock();if(audio.paused)await audio.play();else audio.pause();updatePlayer();
}
async function nextTrack(direction=1) {
  let tracks=state.tracks;
  const selected=state.playlists.find(p=>p.id===playlist);
  if(route==='library'&&selected)tracks=tracks.filter(s=>selected.tracks.includes(s.id));
  else if(route==='library'&&filter==='favorites')tracks=tracks.filter(liked);
  else if(route==='search'&&results)tracks=results;
  const queue=tracks.filter(s=>s.playable);if(!queue.length)return;
  const index=queue.findIndex(s=>s.id===current?.id);await playTrack(queue[(index+direction+queue.length)%queue.length]);
}
async function sendTrack(track) {
  if(demo)return toast('demoSend');if(track.local)return toast('localSave');
  await api('send',{track:track.id});$('dialog').close();toast('sent');
  if(tg?.openTelegramLink&&state.bot)tg.openTelegramLink('https://t.me/'+state.bot);
}
async function renderMix(preview) {
  if(!trackBlob)return toast('chooseFirst');
  const button=$(preview?'preview-mix':'export-mix');button.disabled=true;button.textContent=t('rendering');
  try {
    const blob=await engine.render(trackBlob,preview);
    if(preview) {
      if(previewUrl)URL.revokeObjectURL(previewUrl);previewUrl=URL.createObjectURL(blob);
      audio.src=previewUrl;audio.playbackRate=1;
      // Rendered audio already includes settings: do not apply the live chain twice.
      engine.nodes.headroom.gain.value=1;engine.nodes.filter.gain.value=0;
      await audio.play();toast('previewReady');
    } else {
      const url=URL.createObjectURL(blob),a=document.createElement('a');
      a.href=url;a.download=(current?.title || 'SwiDJ').replace(/[\\/:*?"<>|]/g,'').slice(0,80)+' - SwiDJ mix.wav';
      a.click();setTimeout(()=>URL.revokeObjectURL(url),60000);toast('exportReady');
    }
  } finally {if(route==='studio')render();}
}

document.addEventListener('click',async event=>{
  const button=event.target.closest('button,a,label');if(!button)return;
  try {
    if(button.dataset.go)return navigate(button.dataset.go);
    if(button.dataset.filter){filter=button.dataset.filter;playlist=null;return render();}
    if(button.dataset.playlist){playlist=button.dataset.playlist;return render();}
    if(button.id==='back-playlists'){playlist=null;filter='playlists';return render();}
    if(button.id==='new-playlist')return newPlaylist();
    if(button.dataset.addPlaylist){const track=trackById(button.dataset.track);if(track?.local)return toast('localSave');await mutate({action:'playlist',track:button.dataset.track,playlist:button.dataset.addPlaylist});$('dialog').close();return toast('saved');}
    if(button.dataset.action){
      const track=trackById(button.dataset.track);if(!track)return;
      const action=button.dataset.action;
      if(action==='play')return await playTrack(track);
      if(action==='like'){$('dialog').close();return await favorite(track);}
      if(action==='menu')return trackMenu(track);
      if(action==='playlist')return choosePlaylist(track);
      if(action==='send')return await sendTrack(track);
      if(action==='studio'){$('dialog').close();if(await playTrack(track))navigate('studio');return;}
      if(action==='remove'){
        dialog(t('remove'),`<p class="dialog-copy">${e(t('removeQuestion'))}</p>`,`<button class="btn secondary" value="cancel">${e(t('cancel'))}</button><button class="btn" value="remove">${e(t('remove'))}</button>`);
        $('dialog-form').onsubmit=async event=>{if(event.submitter?.value!=='remove')return;event.preventDefault();try{await mutate({action:'remove',track:track.id});$('dialog').close();toast('removed');}catch(error){report(error);}};return;
      }
    }
    if(button.dataset.bass!==undefined){if(previewUrl&&trackUrl){audio.src=trackUrl;URL.revokeObjectURL(previewUrl);previewUrl=null;}engine.setBass(Number(button.dataset.bass));engine.setSpeed(engine.speed);return render();}
    if(button.id==='reset-fx'){engine.setBass(0);engine.setSpeed(1);if(trackUrl)audio.src=trackUrl;return render();}
    if(button.id==='preview-mix')return await renderMix(true);
    if(button.id==='export-mix')return await renderMix(false);
    if(button.id==='play')return await togglePlay();
    if(button.id==='next')return await nextTrack();
    if(button.id==='previous')return await nextTrack(-1);
    if(button.id==='repeat'){audio.loop=!audio.loop;button.setAttribute('aria-pressed',String(audio.loop));return;}
    if(button.id==='player-like'&&current)return await favorite(current);
    if(['player-art','expand-studio'].includes(button.id))return navigate('studio');
    if(button.id==='language'){
      language=language==='ru'?'en':'ru';try{localStorage.setItem('swidj-language',language);}catch{}
      if(!demo&&!failed)await mutate({action:'language',language});render();
    }
  } catch(error){report(error);}
});
document.addEventListener('submit',async event=>{
  if(event.target.id!=='search-form')return;
  event.preventDefault();if(searching)return;const query=$('search-input').value.trim();if(query.length<2)return;
  searching=true;render();
  try {results=demo?demos.filter(s=>(s.title+' '+s.artist).toLowerCase().includes(query.toLowerCase())):(await (await api('search?q='+encodeURIComponent(query))).json()).tracks;}
  catch(error){report(error);results=[];}finally{searching=false;render();const input=$('search-input');if(input)input.value=query;}
});
document.addEventListener('input',event=>{
  const node=event.target;
  if(node.id==='speed'){
    if(previewUrl&&trackUrl){audio.src=trackUrl;URL.revokeObjectURL(previewUrl);previewUrl=null;engine.setBass(engine.bass);}
    engine.setSpeed(Number(node.value));$('speed-value').textContent=engine.speed.toFixed(2)+'×';
  }
  if(node.id==='volume')audio.volume=Number(node.value);
  if(node.id==='seek'&&Number.isFinite(audio.duration))audio.currentTime=audio.duration*Number(node.value)/1000;
});
document.addEventListener('change',async event=>{
  if(event.target.id!=='local-file')return;
  const file=event.target.files[0];if(!file)return;if(file.size>20*1024**2)return toast('fileTooLarge');
  try {
    const track={id:'local:'+crypto.randomUUID(),title:file.name.replace(/\.[^.]+$/,''),artist:t('uploads'),kind:'upload',playable:true,local:true,blob:file};
    localTracks.clear();localTracks.set(track.id,track);await playTrack(track);render();
  }catch{toast('invalidAudio');}
});
audio.addEventListener('timeupdate',()=>{$('elapsed').textContent=stamp(audio.currentTime);$('duration').textContent=stamp(audio.duration);$('seek').value=Number.isFinite(audio.duration)?String(audio.currentTime/audio.duration*1000):'0';});
audio.addEventListener('play',updatePlayer);audio.addEventListener('pause',updatePlayer);
audio.addEventListener('error',()=>toast('invalidAudio'));
audio.addEventListener('ended',()=>{if(previewUrl){audio.src=trackUrl;URL.revokeObjectURL(previewUrl);previewUrl=null;engine.setBass(engine.bass);engine.setSpeed(engine.speed);updatePlayer();}else if(!audio.loop)nextTrack().catch(report);});
window.addEventListener('keydown',event=>{if(event.code==='Space'&&!['INPUT','TEXTAREA','BUTTON'].includes(document.activeElement?.tagName)&&!$('dialog').open){event.preventDefault();togglePlay().catch(report);}});
window.addEventListener('pagehide',()=>{if(trackUrl)URL.revokeObjectURL(trackUrl);if(previewUrl)URL.revokeObjectURL(previewUrl);});

async function start() {
  if(tg){tg.ready();tg.expand();tg.setHeaderColor?.('#101116');tg.setBackgroundColor?.('#101116');}
  route=['home','search','library','studio'].includes(location.hash.slice(1))?location.hash.slice(1):'home';
  $('content').innerHTML=`<div class="loading">${e(t('loading'))}</div>`;
  if(demo) {
    // Only admit expected demo IDs; malformed local storage cannot become a media URL.
    const saved=demoState&&Array.isArray(demoState.tracks)?demoState:null;
    state={tracks:saved?demos.filter(s=>saved.tracks.some(x=>x.id===s.id)):demos,favorites:saved?.favorites?.filter(id=>demos.some(s=>s.id===id)) || ['demo:0','demo:2'],playlists:Array.isArray(saved?.playlists)?saved.playlists.filter(p=>typeof p.name==='string'&&Array.isArray(p.tracks)).slice(0,20):[{id:'evening',name:language==='ru'?'После заката':'After hours',tracks:['demo:0','demo:3']}],bot:''};
  } else {
    try {state=await (await api('library')).json();language=state.language==='en'?'en':'ru';$('avatar').textContent=(tg?.initDataUnsafe?.user?.first_name || 'S').slice(0,1);}
    catch(error){failed=true;report(error);}
  }
  render();
}
start().catch(report);
