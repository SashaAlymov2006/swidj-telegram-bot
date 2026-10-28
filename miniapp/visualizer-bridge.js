// Loaded only after an explicit click, only when the server enables the feature.
export async function openMusicVideo({blob,title='',language='ru'}){
 if(!document.getElementById('music-video-style'))await new Promise((resolve,reject)=>{const link=document.createElement('link');link.id='music-video-style';link.rel='stylesheet';link.href='/music-video/static/bridge.css';link.onload=resolve;link.onerror=()=>{link.remove();reject(new Error('error'));};document.head.append(link);});
 const english=language==='en',dialog=document.createElement('dialog');dialog.className='music-video-dialog';
 const header=document.createElement('div');header.className='music-video-dialog-header';
 const name=document.createElement('strong');name.textContent=english?'Music video':'Музыкальное видео';
 const close=document.createElement('button');close.type='button';close.textContent=english?'Close':'Закрыть';close.className='btn secondary';
 const frame=document.createElement('iframe');frame.src='/music-video/?lang='+(english?'en':'ru')+(blob?'&new=1':'');frame.title=name.textContent;
 const onMessage=event=>{if(event.origin!==location.origin||event.source!==frame.contentWindow||event.data?.type!=='swidj:music-video-ready')return;frame.contentWindow.postMessage({type:'swidj:music-video',audio:blob,title,language},location.origin);};
 const finish=()=>{window.removeEventListener('message',onMessage);dialog.remove();};
 close.onclick=()=>dialog.close();dialog.addEventListener('close',finish,{once:true});
 header.append(name,close);dialog.append(header,frame);document.body.append(dialog);window.addEventListener('message',onMessage);dialog.showModal();
}
