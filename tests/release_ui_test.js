const source=await Deno.readTextFile(new URL('../miniapp/app.js',import.meta.url));
const funcs=source.slice(source.indexOf('async function loadArtist('),source.indexOf('function trackInfo('));
const assert=v=>{if(!v)throw Error('Release catalog UI assertion failed');};
Deno.test('Albums load on demand; ordered songs retain playback and navigation',async()=>{
 const calls=[];const page={origin:{id:'seed',artist:'Artist'},name:'Artist',source:'all',section:'albums',releases:[],album:null,tracks:[],available:[],next:null,busy:false,ticket:0};
 const api=async path=>{calls.push(path);return {json:async()=>path.includes('album=9')?{name:'Artist',album:{id:'9',title:'Real album',source_url:'https://music.apple.com/de/album/9'},tracks:[{id:'101',title:'First',artist:'Artist',track_number:1},{id:'102',title:'Second',artist:'Artist',track_number:2}]}:{name:'Artist',releases:[{id:'9',title:'Real album',kind:'album',cover:'https://is1.mzstatic.com/image.jpg',release_date:'2026-01-01'}],next_offset:null}};};
 const escape=s=>String(s??'').replaceAll('<','&lt;').replaceAll('"','&quot;');
 const run=new Function('api','page','e',`let artistPage=page;const extraTracks=new Map();let route='search';const render=()=>{},report=e=>{throw e;},t=x=>x,row=t=>'<button data-action="play" data-track="'+t.id+'">'+e(t.title)+'</button>',icon=()=>'';${funcs};return {loadArtist,artistScreen,extraTracks};`)(api,page,escape);
 assert(calls.length===0);await run.loadArtist();assert(calls[0].startsWith('artist/releases?')&&page.releases.length===1);
 assert(run.artistScreen().includes('data-artist-album="9"'));
 page.album=page.releases[0];await run.loadArtist();assert(page.tracks.map(t=>t.track_number).join(',')==='1,2');
 const screen=run.artistScreen();assert(screen.includes('data-action="play"')&&screen.includes('release-back'));
 assert(run.extraTracks.has('101')&&run.extraTracks.has('102'));
});
Deno.test('Artist, remix navigation and the existing version choice remain available',()=>{
 assert(source.includes('data-artist-section=')&&source.includes('artistRemixes')&&source.includes('if(button.dataset.artistAlbum)'));
 assert(source.includes("recordingChoices(await(await api('versions'"));
});
Deno.test('Artist discovery ignores stale searches and does not interrupt playback',async()=>{
 const start=source.indexOf('async function loadDiscovery('),end=source.indexOf('function searchScreen()',start);
 const pending=[];const api=()=>new Promise(resolve=>pending.push(resolve));
 const run=new Function('api',`let searchGeneration=1,searchArtists=[],searchAlbums=[],artistDiscovering=false;const demo=false,route='search',artistPage=null,extraTracks=new Map(),render=()=>{};${source.slice(start,end)};return {loadDiscovery,setGeneration:n=>searchGeneration=n,state:()=>({searchArtists,searchAlbums,artistDiscovering})};`)(api);
 const old=run.loadDiscovery('old',1);run.setGeneration(2);const fresh=run.loadDiscovery('fresh',2);
 pending[0]({json:async()=>({artists:[{id:'old',artist:'Old'}],albums:[]})});await old;
 assert(run.state().searchArtists.length===0&&run.state().artistDiscovering);
 pending[1]({json:async()=>({artists:[{id:'new',artist:'New'}],albums:[]})});await fresh;
 assert(run.state().searchArtists[0].id==='new'&&!run.state().artistDiscovering);
});
Deno.test('Search offers explicit artist cards and album opening instead of an automatic jump',()=>{
 assert(source.includes('function discoveryPanel()')&&source.includes('data-search-album=')&&source.includes('void loadDiscovery(query,generation)'));
 assert(!source.includes('await openArtist(data.artist_suggestion)'));
});
