const source=await Deno.readTextFile(new URL('../miniapp/app.js',import.meta.url));
const block=source.slice(source.indexOf('// Navigation bookmarks contain'),source.indexOf('// End navigation bookmarks.'));
const assert=v=>{if(!v)throw Error('Navigation bookmark assertion failed');};
// A full render harness exercises the actual app navigation functions.
function harness(saved=null,hash=''){
 const storage=new Map(saved?[['test-navigation',JSON.stringify(saved)]]:[]),frames=[];
 const w={scrollY:0,addEventListener:()=>{},scrollTo:({top})=>w.scrollY=top};
 const d={hidden:false,activeElement:{matches:()=>false},addEventListener:()=>{}};
 const run=new Function('window','document','localStorage','requestAnimationFrame','location','setTimeout','clearTimeout',`
 const sessionKey='test';let route='search',searchSource='all',searchQuery='',filter='all',playlist=null,chartCountry='de',chartFilter='',artistPage=null,linkMode=false,searching=false,chartsLoading=false;
 const state={playlists:[{id:'folder'}]},renderContent=()=>{};
 ${block}
 return {render,restoreNavigation,saveNavigation,state:()=>({route,searchQuery,lastSearchQuery,filter,playlist,viewPositions}),set:v=>{if(v.route)route=v.route;if('searching'in v)searching=v.searching;if('artistPage'in v)artistPage=v.artistPage;ignoreScrollUntil=0;}};
 `)(w,d,{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)},cb=>frames.push(cb),{hash},()=>1,()=>{});
 return {run,w,d,storage,flush:()=>{while(frames.length)frames.shift()();}};
}
Deno.test('Search and library keep independent scroll positions across studio navigation',()=>{
 const h=harness();h.run.render();h.flush();h.run.set({route:'search'});h.w.scrollY=540;
 h.run.set({route:'studio'});h.run.render();h.flush();assert(h.w.scrollY===0);
 h.run.set({route:'library'});h.run.render();h.flush();h.run.set({route:'library'});h.w.scrollY=180;
 h.run.set({route:'search'});h.run.render();h.flush();assert(h.w.scrollY===540);
 h.run.set({route:'library'});h.run.render();h.flush();assert(h.w.scrollY===180);
});
Deno.test('Reload restores query, valid playlist and position without audio or media tickets',()=>{
 const h=harness({at:Date.now(),route:'library',query:'Jeff Lorber',submitted:'Jeff Lorber',source:'sc',filter:'playlists',playlist:'folder',positions:{library:120}});
 h.run.restoreNavigation();assert(h.run.state().playlist==='folder'&&h.run.state().searchQuery==='Jeff Lorber');
 h.run.saveNavigation();const saved=h.storage.get('test-navigation');assert(!saved.includes('audio')&&!saved.includes('token'));
 const explicit=harness({at:Date.now(),route:'library'},'#search');explicit.run.restoreNavigation();assert(explicit.run.state().route==='search');
});
Deno.test('Loading placeholders do not overwrite the restored result position; stale frames cannot jump routes',()=>{
 const h=harness();h.run.render();h.flush();h.run.set({route:'search'});h.w.scrollY=640;
 h.run.set({searching:true});h.run.render();h.flush();h.w.scrollY=0;
 h.run.set({searching:false});h.run.render();h.flush();assert(h.w.scrollY===640);
 h.run.set({route:'studio'});h.run.render();h.run.set({route:'search'});h.run.render();h.flush();assert(h.w.scrollY===640);
});
Deno.test('Expired and malformed local state is ignored and restoration never forces the keyboard',()=>{
 const h=harness({at:Date.now()-8*86400000,route:'library',query:'old'});h.run.restoreNavigation();assert(h.run.state().searchQuery==='');
 const k=harness();k.d.activeElement.matches=()=>true;k.w.scrollY=70;k.run.render();k.flush();assert(k.w.scrollY===70);
 assert(!block.includes('.focus(')&&!block.includes('.play('));
});
Deno.test('Immediate restored search does not overwrite its position before the first animation frame',()=>{
 const key=JSON.stringify(['search','all','Song',false,'','','']);
 const h=harness({at:Date.now(),route:'search',query:'Song',submitted:'Song',positions:{[key]:700}});
 h.run.restoreNavigation();h.run.render();h.run.set({searching:true});h.run.render();h.flush();
 h.w.scrollY=0;h.run.set({searching:false});h.run.render();h.flush();assert(h.w.scrollY===700);
});
