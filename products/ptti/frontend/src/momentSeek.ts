/** A saved moment opens exactly at its recorded time; playback may use context. */
export function momentStartMs(startMs:number, play:boolean, contextSeconds:number):number {
 return play ? Math.max(0,startMs-contextSeconds*1000) : startMs;
}
