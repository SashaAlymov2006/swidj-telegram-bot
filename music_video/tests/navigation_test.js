// Uses the actual app functions; no browser/device validation is implied.
const source=await Deno.readTextFile(new URL('../../miniapp/app.js',import.meta.url));
const tabs=source.match(/^function studioTabs\(\).*$/m)?.[0];
const switching=source.match(/if\(button\.dataset\.studioMode\)\{([^\n]+)\}/)?.[1];
if(!tabs||!switching)throw Error('Navigation functions missing');
const assert=(value)=>{if(!value)throw Error('Navigation assertion failed');};
const resolveSource=source.match(/async function videoTrackBlob\(track\)\{[\s\S]*?\n\}/)?.[0];
Deno.test('Video sources use shared bot/app library and local files without applying audio effects',async()=>{
 assert(resolveSource);
 const original=new Blob(['local audio']);const calls=[];
 const resolve=new Function('localTracks','location','demo','api','fetch',resolveSource+';return videoTrackBlob;')(
  new Map([['local:1',{blob:original}]]),{origin:'https://music.example'},false,
  async(path,body)=>{calls.push([path,body.track]);return {json:async()=>({url:'https://music.example/audio-ticket'})};},
  async(url)=>{calls.push(['fetch',url]);return {ok:true,blob:async()=>new Blob(['server audio'])};}
 );
 assert(await resolve({id:'local:1',local:true})===original);
 await resolve({id:'saved-by-bot'});assert(calls[0][0]==='stream'&&calls[0][1]==='saved-by-bot');
 await resolve({id:'saved-by-app',local:true,serverTicket:'own-ticket'});assert(calls.at(-1)[1]==='https://music.example/studio-file/own-ticket');
 assert(!resolveSource.includes('processMix'));
 let rejected=false;try{await resolve({id:'missing',local:true});}catch{rejected=true;}assert(rejected);
});
Deno.test('Audio, DJ and Video are distinct and only one is selected',()=>{
 for(const mode of ['sound','dj','video'])for(const language of ['ru','en']){
  const labels=language==='ru'?{audioTab:'Аудио',videoTab:'Видео'}:{audioTab:'Audio',videoTab:'Video'};
  const html=new Function('djMode','videoMode','musicVideoAvailable','t','st','e',tabs+';return studioTabs();')(mode==='dj',mode==='video',true,key=>labels[key]||key,()=> 'DJ',value=>value);
  assert((html.match(/aria-pressed="true"/g)||[]).length===1);
  assert(html.includes('data-studio-mode="video"'));
  assert(html.includes(labels.audioTab)&&html.includes(labels.videoTab));
 }
 const hidden=new Function('djMode','videoMode','musicVideoAvailable','t','st','e',tabs+';return studioTabs();')(false,false,false,key=>key,key=>key,value=>value);
 assert(!hidden.includes('data-studio-mode="video"'));
});
Deno.test('Switching sections pauses audio but retains the existing mix',()=>{
 const run=new Function('mode',`let djMode=false,videoMode=false,musicVideoAvailable=true,paused=0,djPaused=0,rendered=0;const audio={pause(){paused++}},djRoom={pauseAll(){djPaused++}},button={dataset:{studioMode:mode}},mix={pitch:2,speed:1.2,effects:['reverb']};function render(){rendered++}(function(){${switching}})();return {djMode,videoMode,paused,djPaused,rendered,mix};`);
 for(const mode of ['sound','dj','video']){
  const result=run(mode);assert(result.rendered===1);assert(result.videoMode===(mode==='video'));assert(result.djMode===(mode==='dj'));
  assert(result.mix.pitch===2&&result.mix.speed===1.2&&result.mix.effects[0]==='reverb');
  if(mode==='video')assert(result.paused===1&&result.djPaused===1);
 }
});
