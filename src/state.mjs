/** @typedef {{id:string,mediaId:string,title:string,time:number,note:string,kind:string}} Moment */
/** @typedef {{round:number,pick:string,result:string}} Prediction */
/** @typedef {{version:1,moments:Moment[],predictions:Prediction[]}} State */
/** @returns {State} */
export function emptyState(){return {version:1,moments:[],predictions:[]}}
/** @param {string|null} raw @returns {State} */
export function readState(raw){try{const v=JSON.parse(raw||'null');if(v?.version!==1||!Array.isArray(v.moments)||!Array.isArray(v.predictions))return emptyState();return {version:1,moments:v.moments.filter(m=>typeof m.id==='string'&&typeof m.mediaId==='string'&&typeof m.title==='string'&&typeof m.note==='string'&&typeof m.kind==='string'&&Number.isFinite(m.time)&&m.time>=0).slice(0,500),predictions:v.predictions.filter(p=>Number.isInteger(p.round)&&p.round>=1&&['A','B'].includes(p.pick)&&['A','B'].includes(p.result)).slice(0,500)}}catch{return emptyState()}}
/** @param {State} s @param {Moment} moment @returns {State} */
export function addMoment(s,moment){if(!Number.isFinite(moment.time)||moment.time<0)throw Error('Invalid media time');if(s.moments.some(m=>m.mediaId===moment.mediaId&&Math.abs(m.time-moment.time)<1))return s;return {...s,moments:[moment,...s.moments].slice(0,500)}}
/** @param {State} s @param {number} round @param {string} pick @returns {State} */
export function reveal(s,round,pick){if(!['A','B'].includes(pick))throw Error('Choose a player');if(s.predictions.some(p=>p.round===round))return s;return {...s,predictions:[...s.predictions,{round,pick,result:round%2===1?'B':'A'}].slice(-500)}}
/** @param {number} seconds */
export function clock(seconds){const n=Math.max(0,Math.floor(seconds||0));return `${Math.floor(n/60)}:${String(n%60).padStart(2,'0')}`}
