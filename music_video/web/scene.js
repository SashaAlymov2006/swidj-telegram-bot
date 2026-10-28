const TAU=Math.PI*2;
import {lyricIndex} from './timing.js';
const rand=(i,seed)=>{const n=Math.sin(i*127.1+seed*311.7)*43758.5453;return n-Math.floor(n);};
const hex=c=>[1,3,5].map(i=>parseInt(c.slice(i,i+2),16));
const blend=(a,b,t)=>`rgb(${a.map((v,i)=>Math.round(v*(1-t)+b[i]*t)).join(',')})`;
export function drawScene(ctx,width,height,scene,time,feature,assets={},duration=Infinity){
 const s=scene,w=width,h=height,u=Math.min(w,h),[low,mid,high,rms,beat]=feature,strength=s.strength;
 ctx.clearRect(0,0,w,h);ctx.save();
 const gradient=ctx.createLinearGradient(0,0,0,h);gradient.addColorStop(0,s.background);gradient.addColorStop(1,blend(hex(s.background),hex(s.color2).map(v=>v*.18),1));ctx.fillStyle=gradient;ctx.fillRect(0,0,w,h);
 const background=s.backgroundKind==='video'?assets.video:s.backgroundKind==='image'?assets.background:null;
 if(background&&(background.videoWidth||background.naturalWidth)){
  const iw=background.videoWidth||background.naturalWidth,ih=background.videoHeight||background.naturalHeight,zoom=s.fit==='contain'?1:1+(s.zoom-1)*(.5+.5*Math.sin(time*.2)),scale=(s.fit==='contain'?Math.min:Math.max)(w/iw,h/ih)*zoom;
  ctx.filter=`blur(${s.blur*u/720}px)`;ctx.drawImage(background,(w-iw*scale)*s.panX,(h-ih*scale)*s.panY,iw*scale,ih*scale);ctx.filter='none';ctx.globalAlpha=s.dim;ctx.fillStyle=s.background;ctx.fillRect(0,0,w,h);ctx.globalAlpha=1;
 }
 if(s.vignette){const shade=ctx.createRadialGradient(w/2,h/2,0,w/2,h/2,Math.hypot(w,h)/2);shade.addColorStop(0,'transparent');shade.addColorStop(1,`rgba(0,0,0,${s.vignette*.85})`);ctx.fillStyle=shade;ctx.fillRect(0,0,w,h);}
 const a=hex(s.color),b=hex(s.color2),cx=w*s.logoX,cy=h*s.logoY,radius=u*.19*s.logoSize*(1+(low*.13+beat*.03)*strength*s.pulse),angle=time*s.rotation*.7;
 if(s.preset==='vinyl'){for(let i=0;i<14;i++){ctx.strokeStyle=blend(a,b,i/14);ctx.globalAlpha=.3;ctx.lineWidth=Math.max(1,u*.001);ctx.beginPath();ctx.arc(cx,cy,radius*(1.03+i*.025),0,TAU);ctx.stroke();}ctx.globalAlpha=1;}
 if(s.preset==='tunnel'){for(let i=0;i<9;i++){const phase=(i/9+time*.035)%1,r=u*(.12+phase*.85);ctx.strokeStyle=blend(a,b,phase);ctx.globalAlpha=.15+.4*(1-phase);ctx.lineWidth=u*.002*(1+beat);ctx.beginPath();for(let j=0;j<=6;j++){const theta=j/6*TAU+angle*.2,x=cx+Math.cos(theta)*r,y=cy+Math.sin(theta)*r;j?ctx.lineTo(x,y):ctx.moveTo(x,y);}ctx.stroke();}ctx.globalAlpha=1;}
 if(s.preset==='aurora'){for(let i=0;i<5;i++){ctx.strokeStyle=blend(a,b,i/4);ctx.globalAlpha=.12;ctx.lineWidth=u*(.025+mid*.025);ctx.beginPath();for(let j=0;j<=64;j++){const x=w*j/64,y=h*(.25+i*.09)+Math.sin(j/64*TAU+time*.3+i)*u*(.06+low*.035);j?ctx.lineTo(x,y):ctx.moveTo(x,y);}ctx.stroke();}ctx.globalAlpha=1;}
 if(s.preset==='grid'){ctx.strokeStyle=s.color2;ctx.globalAlpha=.4;ctx.lineWidth=Math.max(1,u*.002);const horizon=h*.55;for(let i=-8;i<=8;i++){ctx.beginPath();ctx.moveTo(w/2+i*w*.035,horizon);ctx.lineTo(w/2+i*w*.2,h);ctx.stroke();}for(let i=0;i<12;i++){const q=(i/12+time*.08)%1,y=horizon+q*q*(h-horizon);ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(w,y);ctx.stroke();}ctx.globalAlpha=1;}
 if(s.preset==='liquid'){for(let i=0;i<5;i++){ctx.fillStyle=blend(a,b,i/5);ctx.globalAlpha=.12;ctx.beginPath();ctx.arc(w*(.5+.4*Math.sin(time*.15+i)),h*(.5+.4*Math.cos(time*.13+i)),u*(.08+.04*mid),0,TAU);ctx.fill();}ctx.globalAlpha=1;}
 if(s.preset==='stage'){for(let i=0;i<5;i++){const x=w*i/4;ctx.fillStyle=blend(a,b,i/5);ctx.globalAlpha=(12+20*low)/255;ctx.beginPath();ctx.moveTo(cx,h*.1);ctx.lineTo(x-u*.1,h);ctx.lineTo(x+u*.1,h);ctx.fill();}ctx.globalAlpha=1;}
 ctx.shadowColor=s.color;ctx.shadowBlur=u*.018*s.glow;
 if(s.particles!=='none')for(let i=0;i<s.particleCount;i++){
  const phase=rand(i,s.seed),angle=rand(i+400,s.seed)*TAU+time*.05,distance=(phase*u*.8+time*18)%(u*.8);
  const x=s.particles==='snow'?rand(i+20,s.seed)*w:cx+Math.cos(angle)*distance,y=s.particles==='snow'?(phase*h+time*22)%h:cy+Math.sin(angle)*distance,size=(1+rand(i+800,s.seed)*2+high*2)*u/720;
  ctx.globalAlpha=(90+130*phase)/255;ctx.fillStyle=ctx.strokeStyle=blend(a,b,phase);ctx.beginPath();ctx.arc(x,y,size,0,TAU);ctx.fill();
  if(s.particles==='stars'){ctx.lineWidth=Math.max(.5,u/1080);ctx.beginPath();ctx.moveTo(x-size*2,y);ctx.lineTo(x+size*2,y);ctx.moveTo(x,y-size*2);ctx.lineTo(x,y+size*2);ctx.stroke();}
 }ctx.globalAlpha=1;
 const bars=feature.slice(5);
 if(s.spectrum==='ring')bars.forEach((energy,i)=>{const angle=i/48*TAU-Math.PI/2,inner=radius+u*.018,outer=inner+energy*u*.11*strength*s.spectrumSize;ctx.strokeStyle=blend(a,b,i/48);ctx.lineWidth=Math.max(2,u*.005);ctx.beginPath();ctx.moveTo(cx+Math.cos(angle)*inner,cy+Math.sin(angle)*inner);ctx.lineTo(cx+Math.cos(angle)*outer,cy+Math.sin(angle)*outer);ctx.stroke();});
 else if(s.spectrum==='bars')bars.forEach((energy,i)=>{const x=w*.12+i*w*.76/48,bh=u*.025+energy*u*.17*strength*s.spectrumSize;ctx.fillStyle=blend(a,b,i/48);ctx.fillRect(x,h*s.spectrumY-bh,w*.76/48*.6,bh);});
 else if(s.spectrum==='mirror')bars.forEach((energy,i)=>{const x=w*.12+i*w*.76/48,bh=u*.012+energy*u*.085*strength*s.spectrumSize;ctx.fillStyle=blend(a,b,i/48);ctx.fillRect(x,h*s.spectrumY-bh,w*.76/48*.6,bh*2);});
 else if(s.spectrum==='wave'){ctx.strokeStyle=s.color;ctx.lineWidth=Math.max(2,u*.005);ctx.beginPath();bars.forEach((energy,i)=>{const x=w*.1+i*w*.8/47,y=h*(s.spectrumY-.05)+Math.sin(i*.55+time*2)*energy*u*.09*strength*s.spectrumSize;i?ctx.lineTo(x,y):ctx.moveTo(x,y);});ctx.stroke();}
 if(s.shape!=='none'){
  const shape=()=>{ctx.beginPath();if(s.shape==='circle')ctx.arc(cx,cy,radius,0,TAU);else{const n=s.shape==='triangle'?3:4;for(let i=0;i<n;i++){const x=cx+Math.cos(angle-Math.PI/2+i*TAU/n)*(radius-2),y=cy+Math.sin(angle-Math.PI/2+i*TAU/n)*(radius-2);i?ctx.lineTo(x,y):ctx.moveTo(x,y);}ctx.closePath();}};
  ctx.save();shape();ctx.clip();ctx.shadowBlur=0;ctx.fillStyle=s.background;ctx.fillRect(cx-radius,cy-radius,radius*2,radius*2);
  if(assets.logo?.naturalWidth){const im=assets.logo,scale=Math.max(radius*2/im.naturalWidth,radius*2/im.naturalHeight);ctx.save();ctx.translate(cx,cy);if(s.spinLogo)ctx.rotate(angle);ctx.drawImage(im,-im.naturalWidth*scale/2,-im.naturalHeight*scale/2,im.naturalWidth*scale,im.naturalHeight*scale);ctx.restore();}ctx.restore();shape();ctx.strokeStyle=s.color;ctx.lineWidth=Math.max(2,u*.004);ctx.stroke();
 }
 ctx.shadowBlur=0;
 if(s.preset==='retro'){ctx.strokeStyle='#0003';ctx.lineWidth=1;for(let y=0;y<h;y+=Math.max(3,Math.round(u*.006))){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(w,y);ctx.stroke();}}
 ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillStyle='#fff';ctx.strokeStyle='#000';ctx.lineWidth=Math.max(1,u/720)*2;
 ctx.fillStyle=s.textColor;
 for(const [text,y,size] of [[s.title,h*s.textY,u*.042*s.textSize],[s.subtitle,h*Math.min(.97,s.textY+.06),u*.025*s.textSize]])if(text){ctx.font=`500 ${size}px "Segoe UI",system-ui,sans-serif`;ctx.strokeText(text,w/2,y,w*.9);ctx.fillText(text,w/2,y,w*.9);}
 if(s.lyricsOn&&assets.lyrics?.length){
  const lines=assets.lyrics,index=lyricIndex(lines,s.start+time-s.lyricsOffset);
  if(index>=0){const cy=h*s.lyricsY,size=u*.034*s.lyricsSize;ctx.fillStyle='rgba(0,0,0,.69)';ctx.fillRect(w*.06,cy-size*2.5,w*.88,size*5);
   for(const offset of [-1,0,1]){if(!lines[index+offset])continue;let text=lines[index+offset].text,face=size*(offset? .72:(s.lyricsStyle==='pulse'?1+beat*.08:1));ctx.font=`500 ${face}px "Segoe UI",system-ui,sans-serif`;let width=ctx.measureText(text).width;if(width>w*.84){face=Math.max(size*.48,face*w*.84/width);ctx.font=`500 ${face}px "Segoe UI",system-ui,sans-serif`;}while(text&&ctx.measureText(text).width>w*.84)text=text.slice(0,-2)+'…';ctx.fillStyle=offset?'#a3acb7':s.lyricsStyle==='fade'?blend([126,138,152],hex(s.textColor),Math.min(1,Math.max(0,(s.start+time-s.lyricsOffset-lines[index].at)/.4))):s.textColor;ctx.strokeText(text,w/2,cy+offset*size*1.55);ctx.fillText(text,w/2,cy+offset*size*1.55);}
  }
 }
 let opacity=s.fadeIn?Math.min(1,time/Math.min(s.fadeIn,duration/2)):1;
 if(s.fadeOut&&Number.isFinite(duration))opacity=Math.min(opacity,Math.max(0,(duration-time)/Math.min(s.fadeOut,duration/2)));
 if(opacity<1){ctx.globalAlpha=1-opacity;ctx.fillStyle='#000';ctx.fillRect(0,0,w,h);}
 ctx.restore();
}
