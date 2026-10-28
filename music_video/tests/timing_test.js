import {lyricIndex} from '../web/timing.js';
const assert=v=>{if(!v)throw Error('Lyric timing assertion failed');};
Deno.test('Lyrics follow seek, trim-relative source clocks and instrumental gaps',()=>{
 const lines=[{at:-.2,text:'opening'},{at:1,text:'next'},{at:2,text:''},{at:3,text:'ending'}];
 assert(lyricIndex(lines,-1)===-1&&lyricIndex(lines,0)===0&&lyricIndex(lines,1.5)===1&&lyricIndex(lines,2.5)===-1&&lyricIndex(lines,3)===3);
});
