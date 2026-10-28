// Headless DOM contract test, not a claim of real-browser/phone validation.
const configuration=JSON.parse(await Deno.readTextFile(new URL('./model-config.json',import.meta.url)));
const html=await Deno.readTextFile(new URL('../web/index.html',import.meta.url));
const nodes=new Map(),all=[],calls=[];let operations=0;
const context=new Proxy({}, {get:(_,key)=>key==='createLinearGradient'||key==='createRadialGradient'?()=>({addColorStop(){}}):(...args)=>{for(const v of args)if(typeof v==='number'&&!Number.isFinite(v))throw Error('Non-finite Canvas geometry');operations++;}});
class Node{
 constructor(tag='div'){this.tagName=tag.toUpperCase();this.dataset={};this.children=[];this.listeners={};this.style={setProperty(){}};this.classList={add(){},remove(){}};this.value='';this.files=[];this.hidden=false;this.disabled=false;this.options=[];this.clientWidth=390;this.currentTime=0;this.duration=2;this.paused=true;this.videoWidth=160;this.videoHeight=90;this.naturalWidth=100;this.naturalHeight=100;this.width=960;this.height=540;all.push(this);}
 set id(v){this._id=v;nodes.set(v,this);}get id(){return this._id;}
 set innerHTML(value){this._html=value;for(const match of value.matchAll(/<([a-z]+)\b([^>]*)>/g)){const n=new Node(match[1]);for(const attr of match[2].matchAll(/([\w-]+)="([^"]*)"/g)){if(attr[1]==='id')n.id=attr[2];else if(attr[1].startsWith('data-'))n.dataset[attr[1].slice(5).replace(/-([a-z])/g,(_,c)=>c.toUpperCase())]=attr[2];else n[attr[1]]=attr[2];}n.parentElement=this;this.children.push(n);}}
 get innerHTML(){return this._html||'';}
 append(...values){for(const n of values){if(n instanceof Node){n.parentElement=this;this.children.push(n);}}}
 before(){}after(){}replaceChildren(...values){this.children=[];this.append(...values);}
 insertAdjacentHTML(_,value){this.innerHTML=value;}
 setAttribute(key,value){this[key]=value;}removeAttribute(key){delete this[key];}
 addEventListener(type,fn){this.listeners[type]=fn;}
 getContext(){return context;}pause(){this.paused=true;}async play(){this.paused=false;}load(){}click(){if(!this.disabled)return this.onclick?.();}
 get parentElement(){return this._parent||body;}set parentElement(value){this._parent=value;}
}
const body=new Node('body');body.innerHTML=html;
const footer=new Node();footer.className='footer-note';
globalThis.document={body,head:new Node('head'),documentElement:{},hidden:false,activeElement:null,getElementById:id=>nodes.get(id)||null,createElement:tag=>new Node(tag),querySelector:()=>footer,querySelectorAll:selector=>{const key=selector.match(/^\[data-([^\]]+)\]$/)?.[1]?.replace(/-([a-z])/g,(_,c)=>c.toUpperCase());return key?all.filter(n=>key in n.dataset):[];},addEventListener(){}};
const memory=new Map();Object.defineProperty(globalThis,'localStorage',{configurable:true,value:{getItem:key=>memory.get(key)||null,setItem:(key,value)=>memory.set(key,value)}});
globalThis.location=new URL('https://music.example/music-video/?lang=ru&new=1');
globalThis.window={Telegram:{WebApp:{initData:'fixture'}},addEventListener(){}};window.parent=window;
globalThis.requestAnimationFrame=()=>0;globalThis.Image=class extends Node{set src(value){this._src=value;queueMicrotask(()=>this.onload?.());}};
globalThis.fetch=async(url,options={})=>{
 calls.push([String(url),options]);let value={};
 if(url==='api/config')value={...configuration,dev:true,profile:'fixture'};
 else if(url==='api/history')value={jobs:[]};
 else if(url==='api/settings')value={files:{settings:'files/settings'}};
 else if(String(url).startsWith('api/features/'))value={rate:30,offset:0,values:Array.from({length:60},()=>Array(53).fill(.3))};
 else if(url==='api/drafts'||url==='api/jobs/draft'||String(url).startsWith('api/assets/'))value={id:'draft',kind:'draft',state:'ready',expires:Date.now()/1000+3600,duration:2,backgroundKind:'color',files:{audio:'files/audio'}};
 else if(String(url).startsWith('api/render/'))value={id:'video',kind:'video',state:'complete',scene:JSON.parse(options.body),files:{result:'files/result'}};
 return {ok:true,json:async()=>value};
};
await import('../web/editor.js');
for(let i=0;i<30&&!nodes.get('prepare').onclick;i++)await Promise.resolve();
const assert=v=>{if(!v)throw Error('Editor flow assertion failed');};
Deno.test('Editor prepares audio, edits and undoes, updates only images, previews and exports',async()=>{
 assert(nodes.get('prepare').onclick);
 const file=new File(['fixture'],'audio.wav',{type:'audio/wav'});nodes.get('audio-file').files=[file];nodes.get('audio-file').onchange();
 await nodes.get('prepare').onclick();assert(!nodes.get('render').disabled);
 nodes.get('logoSize').value='1.2';nodes.get('logoSize').listeners.input();nodes.get('undo').click();assert(Number(nodes.get('logoSize').value)===1);
 nodes.get('style-name').value='My design';nodes.get('save-preset').click();assert([...memory.keys()].some(k=>k.includes('styles')));
 nodes.get('logo-file').files=[new File(['picture'],'logo.png')];nodes.get('logo-file').onchange();await nodes.get('prepare').onclick();
 const update=calls.find(([url])=>url==='api/assets/draft');assert(update&&!update[1].body.has('audio')&&update[1].body.has('logo'));
 await nodes.get('sample-render').onclick();const sample=calls.filter(([url])=>url==='api/render/draft').at(-1);assert(JSON.parse(sample[1].body).resolution===720&&!nodes.get('render-preview').hidden);
 await nodes.get('render').onclick();assert(!nodes.get('download').hidden&&operations>0);
 await nodes.get('export-style').onclick();assert(!nodes.get('settings-download').hidden&&nodes.get('settings-download').href==='files/settings');
 nodes.get('language').click();assert(document.documentElement.lang==='en');
 nodes.get('logoX').value='.3';nodes.get('logoX').listeners.input();
 globalThis.location=new URL('https://music.example/music-video/?lang=en');
 await import('../web/editor.js?restore-test');
 for(let i=0;i<60&&nodes.get('play').disabled;i++)await Promise.resolve();
 assert(Number(nodes.get('logoX').value)===.3&&!nodes.get('play').disabled);
});
