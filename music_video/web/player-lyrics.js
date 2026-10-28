import {lyricIndex} from './timing.js';
const instances=new WeakMap();let stylePromise;
const words={ru:{read:'Читать',sync:'Под музыку',close:'Закрыть текст',loading:'Ищу текст…',empty:'Текст для этой записи не найден.',source:'Источник',play:'Слушать',pause:'Пауза',delay:'Сдвиг строк, с'},en:{read:'Read',sync:'With music',close:'Close lyrics',loading:'Finding lyrics…',empty:'No lyrics found for this recording.',source:'Source',play:'Play',pause:'Pause',delay:'Lyrics delay, s'}};
export function originalClock({time=0,processed=false,start=0,speed=1}){return processed?start+time*speed:time;}
export function lyricModes(matches,timed){return {read:matches.length>0||Boolean(timed?.available&&timed.lines?.length),sync:Boolean(timed?.available&&timed.lines?.length)};}
function styles(){
 if(!stylePromise)stylePromise=new Promise((resolve,reject)=>{const link=document.createElement('link');link.rel='stylesheet';link.href='/music-video/static/player-lyrics.css';link.onload=resolve;link.onerror=()=>{link.remove();stylePromise=null;reject(Error('styles'));};document.head.append(link);});
 return stylePromise;
}
export async function openPlayerLyrics({host,dialog,track,audio,language='ru',plain,timed,clock,isCurrent,seek,toggle}){
 if(instances.has(host)){instances.get(host).show();return;}
 await styles();if(!host.isConnected||!dialog.open||!isCurrent())return;if(instances.has(host)){instances.get(host).show();return;}
 const t=words[language]||words.ru,panel=document.createElement('section');panel.className='player-lyrics-panel';panel.setAttribute('aria-label',t.read);
 const header=document.createElement('div');header.className='player-lyrics-header';
 const read=document.createElement('button'),sync=document.createElement('button'),close=document.createElement('button'),play=document.createElement('button');
 for(const button of [read,sync,close,play])button.type='button';read.textContent=t.read;sync.textContent=t.sync;close.textContent=t.close;sync.hidden=true;
 header.append(read,sync,play,close);const artist=document.createElement('p');artist.className='player-lyrics-credit';
 const choice=document.createElement('select');choice.hidden=true;choice.setAttribute('aria-label',t.read);
 const content=document.createElement('div');content.className='player-lyrics-content';content.setAttribute('role','region');content.textContent=t.loading;
 const source=document.createElement('a');source.textContent=t.source;source.target='_blank';source.rel='noopener noreferrer';source.hidden=true;
 const adjustment=document.createElement('label');adjustment.className='player-lyrics-delay';adjustment.hidden=true;const label=document.createElement('span');label.textContent=t.delay;const input=document.createElement('input');Object.assign(input,{type:'range',min:-10,max:10,step:.1,value:0});const output=document.createElement('output');output.textContent='0';adjustment.append(label,input,output);
 panel.append(header,artist,choice,content,adjustment,source);host.append(panel);
 let alive=true,mode='read',matches=[],timing=null,selection=0,rows=[],active=-2,frame=0,lastFrame=0;
 const visible=()=>alive&&host.isConnected&&dialog.open&&!panel.hidden&&isCurrent();
 function sourceLink(item){const url=item?.source_url||'';source.hidden=!/^https:\/\/(?:lrclib\.net|api\.lyrics\.ovh)\//.test(url);if(!source.hidden)source.href=url;}
 function update(){
  if(!host.isConnected||!isCurrent())return destroy();
  if(!visible())return;
  const current=clock();play.textContent=audio.paused?t.play:t.pause;
  if(current.canSync===false&&mode==='sync'){mode='read';render();return;}
  sync.hidden=!lyricModes(matches,timing).sync||current.canSync===false;
  if(mode!=='sync')return;
  const index=lyricIndex(timing.lines,originalClock(current)-Number(input.value));if(index===active)return;active=index;
  rows.forEach((row,i)=>{row.classList.toggle('active',i===index);row.setAttribute('aria-current',i===index?'true':'false');});
  const row=rows[index];if(row){const top=Math.max(0,row.offsetTop-content.clientHeight/2+row.offsetHeight/2);content.scrollTo({top,behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});}
 }
 function tick(now){frame=0;if(!visible()||mode!=='sync'||audio.paused)return;if(now-lastFrame>100){lastFrame=now;update();}frame=requestAnimationFrame(tick);}
 function start(){if(!frame&&visible()&&mode==='sync'&&!audio.paused)frame=requestAnimationFrame(tick);}
 function render(){
  content.replaceChildren();active=-2;rows=[];read.setAttribute('aria-pressed',String(mode==='read'));sync.setAttribute('aria-pressed',String(mode==='sync'));adjustment.hidden=mode!=='sync';choice.hidden=mode!=='read'||matches.length<2;
  if(mode==='sync'){
   artist.textContent=timing.artist+' · '+timing.title;sourceLink(timing);
   for(const line of timing.lines){const row=document.createElement('button');row.type='button';row.className='player-lyric-line';row.textContent=line.text||'♪';row.disabled=!line.text;row.onclick=()=>{if(visible()&&clock().canSync!==false){seek(line.at+Number(input.value));update();}};rows.push(row);content.append(row);}
  }else{
   const item=matches[selection];artist.textContent=item?[item.artist,item.title].filter(Boolean).join(' · '):track.title;sourceLink(item);const text=document.createElement('pre');text.className='player-lyrics-plain';text.textContent=item?.text||t.empty;content.append(text);
  }
  update();start();
 }
 function hide(){panel.hidden=true;if(frame)cancelAnimationFrame(frame);frame=0;}
 function show(){panel.hidden=false;update();start();}
 function destroy(){if(!alive)return;alive=false;if(frame)cancelAnimationFrame(frame);for(const event of ['timeupdate','seeked','ratechange','play','pause'])audio.removeEventListener(event,onAudio);dialog.removeEventListener('close',destroy);instances.delete(host);}
 function onAudio(){update();start();}
 read.onclick=()=>{mode='read';render();};sync.onclick=()=>{if(!sync.hidden){mode='sync';render();}};close.onclick=hide;play.onclick=()=>{if(visible())Promise.resolve(toggle()).then(onAudio).catch(()=>{});};input.oninput=()=>{output.textContent=input.value;active=-2;update();};choice.onchange=()=>{selection=Number(choice.value)||0;render();};
 for(const event of ['timeupdate','seeked','ratechange','play','pause'])audio.addEventListener(event,onAudio);dialog.addEventListener('close',destroy,{once:true});instances.set(host,{show,destroy});play.textContent=audio.paused?t.play:t.pause;
 let plainDone=false,timedDone=false,plainMatches=[];
 function refresh(){
  if(!alive||!host.isConnected||!isCurrent())return destroy();
  const previous=matches[selection],key=previous?[previous.artist,previous.title,previous.text].join('\n'):null;
  matches=plainMatches.length?plainMatches:timing?.available?[{...timing,text:timing.lines.map(row=>row.text).join('\n')}]:[];
  const found=key?matches.findIndex(item=>[item.artist,item.title,item.text].join('\n')===key):-1;selection=Math.max(0,found);choice.replaceChildren();
  for(let i=0;i<matches.length;i++){const option=document.createElement('option');option.value=String(i);option.textContent=[matches[i].artist,matches[i].title].filter(Boolean).join(' · ');choice.append(option);}choice.value=String(selection);
  if(matches.length||plainDone&&timedDone)render();
 }
 await Promise.allSettled([
  Promise.resolve().then(plain).then(data=>{plainMatches=Array.isArray(data?.matches)?data.matches:[];plainDone=true;refresh();},()=>{plainDone=true;refresh();}),
  Promise.resolve().then(timed).then(data=>{timing=data?.available&&Array.isArray(data.lines)?data:null;timedDone=true;refresh();},()=>{timedDone=true;refresh();})
 ]);
}
