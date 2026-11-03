import assert from 'node:assert/strict';
import {assertPublicArtifact} from './artifact-isolation.mjs';
assertPublicArtifact('assets/app.js',Buffer.from('if (value.visibility !== "PRIVATE_REVIEW_ONLY") reject("HANDOFF_VISIBILITY_REJECTED");'));
for(const [name,text]of [['data/report.json','{"visibility":"PRIVATE_REVIEW_ONLY"}'],['assets/app.js','const report={visibility:"PRIVATE_REVIEW_ONLY"};'],['data/web-internal-review.json','{}'],['assets/app.js','ptti.cinema-source-review/0.1'],['assets/app.js','INTERNAL_REVIEW_ONLY']])assert.throws(()=>assertPublicArtifact(name,Buffer.from(text)));
console.log('PASS: validator enum comparison allowed; five actual private/internal payload, path and marker cases rejected.');
