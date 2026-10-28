export function lyricIndex(lines,time){
 let left=0,right=lines.length;
 while(left<right){const middle=(left+right)>>1;if(lines[middle].at<=time)left=middle+1;else right=middle;}
 const index=left-1;return index>=0&&lines[index]?.text?index:-1;
}
