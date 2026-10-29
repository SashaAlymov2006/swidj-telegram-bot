import {movement} from '../web/state.js';
import {drawScene} from '../web/scene.js';
const config=JSON.parse(await Deno.readTextFile(new URL('./model-config.json',import.meta.url)));
const cases=JSON.parse(await Deno.readTextFile(new URL('./motion-cases.json',import.meta.url)));
const assert=value=>{if(!value)throw Error('Animation assertion failed');};
Deno.test('Preview geometry agrees with the export renderer for every motion and pulse mode',()=>{
 for(const row of cases){const actual=movement({...config.defaults,...row.scene},row.time,row.feature,row.width,row.height);actual.forEach((v,i)=>assert(Math.abs(v-row.expected[i])<1e-7));}
});
Deno.test('Every ready template draws finite geometry in phone and desktop formats',()=>{
 let count=0;const ctx=new Proxy({}, {get:(_,key)=>key==='createLinearGradient'||key==='createRadialGradient'?()=>({addColorStop(){}}):key==='measureText'?value=>({width:value.length*12}):(...args)=>{for(const value of args)if(typeof value==='number')assert(Number.isFinite(value));count++;}});
 for(const [key,preset] of Object.entries(config.presets))for(const [w,h] of [[390,844],[1440,900]])for(const time of [0,.8,4]){
  drawScene(ctx,w,h,{...config.defaults,...preset,preset:key,lyricsOn:true,lyricsBackdrop:'none'},time,Array(53).fill(.4),{lyrics:[{at:0,text:'Fixture'},{at:1,text:'Next'}]},10);
 }
 assert(count>1000);
});
