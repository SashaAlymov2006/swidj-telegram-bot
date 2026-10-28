import {normalize,presetScene,SceneHistory} from '../web/state.js';
const config=JSON.parse(await Deno.readTextFile(new URL('./model-config.json',import.meta.url)));
const assert=v=>{if(!v)throw Error('Scene state assertion failed');};
Deno.test('Imported styles cannot inject invalid controls or arbitrary fields',()=>{
 const value=normalize({fps:120,logoSize:Infinity,logoX:-50,textColor:'url(bad)',title:'hello\nworld',unknown:1},config.defaults,config.presets);
 assert(value.fps===30&&value.logoSize===1&&value.logoX===.1&&value.textColor==='#ffffff'&&value.title==='helloworld'&&!('unknown' in value));
});
Deno.test('Undo groups slider gestures, redo works, and new edits clear redo',()=>{
 const history=new SceneHistory(),a={x:0},b={x:1},c={x:2};history.capture(a,'x',1000);history.capture(b,'x',1100);assert(history.undo(c).x===0);assert(history.redo(a).x===2);history.undo(c);history.capture(a,'y',2000);assert(!history.future.length);
});
Deno.test('Presets do not retain accidental settings from the previous preset',()=>{
 const current={...config.defaults,title:'My song',start:12,end:45,particleCount:200,blur:20};const value=presetScene(current,config.defaults,config.presets.neon,'neon');
 assert(value.title==='My song'&&value.start===12&&value.end===45&&value.blur===0&&value.particleCount===36);
});
