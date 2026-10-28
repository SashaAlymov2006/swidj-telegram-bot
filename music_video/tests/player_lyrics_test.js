import {originalClock,lyricModes,openPlayerLyrics} from '../web/player-lyrics.js';
const assert=v=>{if(!v)throw Error('Player lyrics assertion failed');};
class Node extends EventTarget{
 constructor(tag='div'){super();this.tagName=tag;this.children=[];this.isConnected=true;this.hidden=false;this.open=true;this.paused=false;this.classList={toggle:(key,value)=>{this[key]=value;}};this.offsetTop=0;this.offsetHeight=40;this.clientHeight=180;}
 append(...nodes){this.children.push(...nodes);for(const node of nodes)if(node.tagName==='link')queueMicrotask(()=>node.onload());}
 replaceChildren(...nodes){this.children=[];this.append(...nodes);}
 setAttribute(key,value){this[key]=value;}scrollTo(){}remove(){}
}
globalThis.document={head:new Node(),createElement:tag=>new Node(tag)};
globalThis.matchMedia=()=>({matches:true});globalThis.requestAnimationFrame=()=>1;globalThis.cancelAnimationFrame=()=>{};
Deno.test('Player offers reading and synchronized lines without restarting audio; hide/reopen and seek work',async()=>{
 const host=new Node(),dialog=new Node(),audio=new Node('audio');let time=.5,plays=0,seeks=[];
 const options={host,dialog,audio,track:{title:'Fixture'},language:'ru',isCurrent:()=>true,
 plain:async()=>({matches:[{title:'Fixture',artist:'Artist',text:'Plain fixture'}]}),
 timed:async()=>({available:true,title:'Fixture',artist:'Artist',lines:[{at:0,text:'First'},{at:1,text:'Second'}]}),
 clock:()=>({time}),seek:value=>{seeks.push(value);time=value;},toggle:()=>{plays++;}};
 await openPlayerLyrics(options);const panel=host.children[0],[header,,choice,content]=panel.children,[read,sync,play,close]=header.children;
 assert(read.textContent==='Читать'&&sync.textContent==='Под музыку'&&!sync.hidden);assert(content.children[0].textContent==='Plain fixture'&&plays===0);
 sync.onclick();assert(content.children[0].active===true);time=1.2;audio.dispatchEvent(new Event('timeupdate'));assert(content.children[1].active===true);
 content.children[0].onclick();assert(seeks[0]===0);read.onclick();assert(content.children[0].textContent==='Plain fixture');
 close.onclick();assert(panel.hidden);await openPlayerLyrics(options);assert(!panel.hidden&&host.children.length===1&&plays===0&&choice.hidden);
 play.onclick();assert(plays===1);dialog.dispatchEvent(new Event('close'));
});
Deno.test('Unsynchronized lyrics remain readable; unavailable timings never show sync mode',async()=>{
 const host=new Node();await openPlayerLyrics({host,dialog:new Node(),audio:new Node(),track:{title:'Fixture'},isCurrent:()=>true,plain:async()=>({matches:[{text:'Only plain'}]}),timed:async()=>({available:false}),clock:()=>({time:0}),seek(){},toggle(){}});
 assert(host.children[0].children[0].children[1].hidden);assert(host.children[0].children[3].children[0].textContent==='Only plain');
 assert(originalClock({time:2,processed:true,start:5,speed:1.5})===8);assert(originalClock({time:2,processed:false,start:5,speed:2})===2);
 assert(!lyricModes([],{available:false}).sync);
});
