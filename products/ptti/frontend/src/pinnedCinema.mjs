import {PUBLIC_PROJECTION_SHA256,parsePinnedMatchContract} from './match-contract-v1.mjs';
import {validateProjection} from './cinemaProjection.mjs';
export async function loadPinnedCinema(raw){
 const bytes=new TextEncoder().encode(raw);
 if(!globalThis.crypto?.subtle)throw Error('PROJECTION_CRYPTO_UNAVAILABLE');
 const digest=await crypto.subtle.digest('SHA-256',bytes);
 const hash=Array.from(new Uint8Array(digest),b=>b.toString(16).padStart(2,'0')).join('');
 if(hash!==PUBLIC_PROJECTION_SHA256)throw Error('PROJECTION_SHA_MISMATCH');
 const projection=validateProjection(JSON.parse(raw));
 const matches=await Promise.all(projection.matches.map(m=>parsePinnedMatchContract(bytes,m.match_id)));
 return {projection,matches};
}
