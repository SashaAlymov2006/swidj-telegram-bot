export const ranges={strength:[0,3,.05],glow:[0,1,.05],particleCount:[0,200,1],rotation:[-1,1,.05],dim:[0,.95,.05],zoom:[1,1.5,.01],logoX:[.1,.9,.01],logoY:[.1,.9,.01],logoSize:[.4,1.6,.05],pulse:[0,2,.05],spectrumY:[.2,.95,.01],spectrumSize:[.5,1.5,.05],panX:[0,1,.01],panY:[0,1,.01],blur:[0,20,.5],vignette:[0,1,.05],textY:[.1,.9,.01],textSize:[.5,1.5,.05],fadeIn:[0,3,.1],fadeOut:[0,3,.1],start:[0,86400,.1],end:[0,86400,.1],seed:[0,2147483647,1],lyricsY:[.15,.9,.01],lyricsSize:[.6,1.4,.05],lyricsOffset:[-10,10,.1],lyricsOpacity:[0,.9,.05],animationSpeed:[.2,2,.05],motionAmount:[0,1,.05]};
const enums={shape:['none','circle','triangle','square','hexagon','star'],spectrum:['none','ring','bars','wave','mirror','ripple','dualwave'],particles:['none','stars','sparks','snow'],backgroundKind:['color','image','video'],aspect:['landscape','portrait','square'],fit:['cover','contain'],resolution:[720,1080],fps:[30,60],version:[1]};
enums.lyricsBackdrop=['panel','none'];enums.pulseMode=['bass','beat','breath','double','off'];enums.motion=['still','float','orbit','sway'];
enums.lyricsStyle=['highlight','fade','pulse'];
export function normalize(value,defaults,presets={}){
 const result={...defaults};if(!value||typeof value!=='object'||Array.isArray(value))return result;
 for(const key of Object.keys(defaults)){
  const v=value[key];if(key==='preset'){if(Object.hasOwn(presets,v))result[key]=v;}
  else if(enums[key]){if(enums[key].includes(v))result[key]=v;}
  else if(typeof defaults[key]==='boolean'){if(typeof v==='boolean')result[key]=v;}
  else if(ranges[key]){if(typeof v==='number'&&Number.isFinite(v)){const [low,high]=ranges[key];result[key]=Math.max(low,Math.min(high,v));if(key==='seed'||key==='particleCount')result[key]=Math.round(result[key]);}}
  else if(/^(color|color2|background|textColor)$/.test(key)){if(typeof v==='string'&&/^#[a-f\d]{6}$/i.test(v))result[key]=v;}
  else if(key==='title'||key==='subtitle'){if(typeof v==='string')result[key]=v.replace(/[\x00-\x1f]/g,'').slice(0,key==='title'?120:100);}
 }
 if(result.end&&result.end<=result.start)result.end=0;return result;
}
export function presetScene(scene,defaults,preset,key){
 const keep=Object.fromEntries(['title','subtitle','start','end','fps','resolution','aspect','backgroundKind','lyricsOn','lyricsOffset'].filter(k=>k in scene).map(k=>[k,scene[k]]));
 return {...defaults,...preset,...keep,preset:key};
}
export class SceneHistory{
 constructor(){this.past=[];this.future=[];this.key=null;this.at=0;}
 capture(scene,key='',now=Date.now()){
  const value=JSON.stringify(scene);if(key&&key===this.key&&now-this.at<500){this.at=now;return;}
  if(this.past.at(-1)!==value)this.past.push(value);this.past=this.past.slice(-50);this.future=[];this.key=key;this.at=now;
 }
 undo(scene){if(!this.past.length)return scene;this.future.push(JSON.stringify(scene));this.key=null;return JSON.parse(this.past.pop());}
 redo(scene){if(!this.future.length)return scene;this.past.push(JSON.stringify(scene));this.key=null;return JSON.parse(this.future.pop());}
}

export function movement(s,t,features,w,h){
 const [low,mid,high,rms,beat]=features,u=Math.min(w,h),amount=s.motionAmount;
 const response={bass:low*.13+beat*.03,beat:beat*.18,breath:(.5+.5*Math.sin(t*2))*.1+low*.08,double:beat*(.1+.08*(.5+.5*Math.sin(t*8)))+low*.04,off:0}[s.pulseMode];
 let cx=w*s.logoX,cy=h*s.logoY,angle=t*s.rotation*.7;
 if(s.motion==='float'){cx+=Math.sin(t*.7)*u*.025*amount;cy+=Math.sin(t*.9)*u*.04*amount;}
 if(s.motion==='orbit'){cx+=Math.sin(t*.65)*u*.07*amount;cy+=Math.cos(t*.65)*u*.04*amount;}
 if(s.motion==='sway')angle+=Math.sin(t*1.4)*.3*amount;
 return [cx,cy,u*.19*s.logoSize*(1+response*s.strength*s.pulse),angle];
}
