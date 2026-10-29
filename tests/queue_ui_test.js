const source=await Deno.readTextFile(new URL('../miniapp/app.js',import.meta.url));
const pause=source.match(/function queuePause\([^]*?\nasync function queueFetch/)?.[0].replace(/\nasync function queueFetch$/,'');
const request=source.match(/async function queueFetch\([^]*?\nasync function processMix/)?.[0].replace(/\nasync function processMix$/,'');
const assert=v=>{if(!v)throw Error('Queue UI assertion failed');};
Deno.test('Busy responses retry automatically, preserve the payload and display polite waiting',async()=>{
 let calls=0,waits=0,notices=0,cancelled=0;const options={body:'same original payload'};
 const run=new Function('fetch','queuePause',request+';return queueFetch;')(async(url,value)=>{assert(value===options);return ++calls<3?{status:429,body:{cancel:async()=>cancelled++}}:{status:200};},async()=>{waits++;});
 const response=await run('/api/link',options,()=>notices++);assert(response.status===200&&calls===3&&waits===2&&notices===2&&cancelled===2);
 assert(source.includes('обработка начнётся автоматически')&&source.includes('yours will start automatically'));
});
Deno.test('Stopping a queued link cancels retry waiting immediately',async()=>{
 const wait=new Function(pause+';return queuePause;')();const controller=new AbortController();
 const pending=wait(controller.signal,30000);controller.abort();let cancelled=false;
 try{await pending;}catch(error){cancelled=error.name==='AbortError';}assert(cancelled);
});
