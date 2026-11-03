import assert from 'node:assert/strict';
export function assertPublicArtifact(name, bytes) {
 assert(!/(^|\/)(?:cinema-source-review-internal|featured-sources-internal-review|match-library-internal-review|web-internal-review)(?:\.|\/|$)/i.test(name),'Internal artifact filename');
 const text=Buffer.from(bytes).toString('utf8');
 for(const marker of ['ptti.cinema-source-review/0.1','INTERNAL_REVIEW_ONLY','featured-sources-internal-review.json'])assert(!text.includes(marker),'Internal artifact marker: '+marker);
 // A validation comparison is application logic. A serialized private visibility
 // property is private content and must still be refused, including embedded JS objects.
 assert(!/(?:"visibility"|'visibility'|\bvisibility)\s*:\s*["']PRIVATE_REVIEW_ONLY["']/.test(text),'Private report payload');
 if(name.endsWith('.json')) {const value=JSON.parse(text);const visit=v=>{if(v&&typeof v==='object'){assert(v.visibility!=='PRIVATE_REVIEW_ONLY','Private report payload');for(const child of Object.values(v))visit(child);}};visit(value);}
}
