import assert from 'node:assert/strict';
import {mkdtempSync,writeFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {spawnSync} from 'node:child_process';
import {pathToFileURL} from 'node:url';

const folder=mkdtempSync(join(tmpdir(),'ptti-watch-routing-'));
try{
  const compiled=spawnSync(process.execPath,['node_modules/typescript/bin/tsc','../playback-core/adapters/watchRoutingContract.ts','--target','ES2022','--module','ES2022','--strict','--skipLibCheck','--outDir',folder],{encoding:'utf8'});
  assert.equal(compiled.status,0,compiled.stdout+compiled.stderr);
  writeFileSync(join(folder,'package.json'),' {"type":"module"}');
  const {WATCH_ROUTING_CONTRACT,evaluateWatchRoute,classifyWatchFailure}=await import(pathToFileURL(join(folder,'watchRoutingContract.js')));
  const base={sourceReference:'VERIFIED',viewingPermission:'PUBLIC_PLATFORM_PAGE',playbackEvidence:'NOT_TESTED'};

  const embed=evaluateWatchRoute({...base,mode:'OFFICIAL_EMBED',playbackType:'OFFICIAL_EMBED',embedPermission:'ALLOWED'});
  assert.equal(embed.state,'ELIGIBLE');
  assert.equal(embed.playbackEvidence,'NOT_TESTED','embedding permission does not claim actual playback');
  assert.equal(evaluateWatchRoute({...base,mode:'OFFICIAL_EMBED',playbackType:'OFFICIAL_EMBED',embedPermission:'UNKNOWN'}).reason,'EMBED_PERMISSION_UNKNOWN');
  assert.equal(evaluateWatchRoute({...base,mode:'OFFICIAL_EMBED',playbackType:'OFFICIAL_EMBED',embedPermission:'DENIED'}).reason,'EMBED_PERMISSION_DENIED');

  const page=evaluateWatchRoute({...base,mode:'OFFICIAL_PAGE',playbackType:'OFFICIAL_PAGE'});
  assert.equal(page.state,'ELIGIBLE','official page may be opened without claiming its playback works');
  assert.equal(page.playbackEvidence,'NOT_TESTED');
  assert.equal(evaluateWatchRoute({...base,mode:'OFFICIAL_PAGE',playbackType:'AUTHORIZED_STREAM'}).reason,'ROUTE_TYPE_MISMATCH');

  const authorized={...base,mode:'AUTHORIZED_SOURCE',viewingPermission:'AUTHORIZED',playbackType:'AUTHORIZED_STREAM',rightsEvidence:'VERIFIED'};
  assert.equal(evaluateWatchRoute(authorized).state,'ELIGIBLE');
  assert.equal(evaluateWatchRoute({...authorized,rightsEvidence:'UNKNOWN'}).reason,'RIGHTS_EVIDENCE_REQUIRED');
  assert.equal(evaluateWatchRoute({...authorized,viewingPermission:'PUBLIC_PLATFORM_PAGE'}).reason,'VIEW_PERMISSION_DENIED');
  assert.equal(evaluateWatchRoute({...authorized,sourceReference:'UNKNOWN'}).reason,'SOURCE_REFERENCE_UNVERIFIED');

  const replay={mode:'REPLAY',replayType:'LOCAL_FILE',sourceReference:'MISSING',viewingPermission:'UNKNOWN',localMedia:'AVAILABLE',localSelection:'USER_SELECTED',localViewingConfirmation:'USER_CONFIRMED'};
  assert.equal(evaluateWatchRoute(replay).state,'ELIGIBLE','local replay requires explicit user selection, confirmation, and an available file');
  assert.equal(evaluateWatchRoute({...replay,localMedia:'MISSING'}).reason,'LOCAL_MEDIA_UNAVAILABLE');
  assert.equal(evaluateWatchRoute({...replay,localSelection:'NOT_SELECTED'}).reason,'LOCAL_MEDIA_NOT_SELECTED');
  assert.equal(evaluateWatchRoute({...replay,localViewingConfirmation:'UNKNOWN'}).reason,'LOCAL_VIEW_PERMISSION_UNKNOWN');
  assert.equal(evaluateWatchRoute({...replay,localViewingConfirmation:'DENIED'}).reason,'LOCAL_VIEW_PERMISSION_DENIED');
  assert.equal(evaluateWatchRoute({...replay,replayType:'AUTHORIZED_ON_DEMAND',sourceReference:'VERIFIED',viewingPermission:'AUTHORIZED',playbackType:'AUTHORIZED_REPLAY',rightsEvidence:'VERIFIED'}).state,'ELIGIBLE');

  const score={...base,mode:'LIVE_SCORE',liveScore:'LIVE_VERIFIED'};
  const scoreOnly=evaluateWatchRoute(score);
  assert.equal(scoreOnly.state,'SCORE_ONLY');
  assert.equal(scoreOnly.playbackEvidence,'NOT_TESTED');
  assert.equal(evaluateWatchRoute({...score,liveScore:'UNKNOWN'}).reason,'LIVE_SCORE_UNVERIFIED');

  const forbidden=classifyWatchFailure({source:'HTTP',status:403});
  assert.equal(forbidden.code,'HTTP_FORBIDDEN');
  assert.notEqual(forbidden.code,'REGION_RESTRICTED','HTTP 403 alone must not be labeled a region restriction');
  assert.equal(classifyWatchFailure({source:'HTTP',status:401}).code,'HTTP_UNAUTHORIZED');
  assert.notEqual(classifyWatchFailure({source:'HTTP',status:401}).code,'LOGIN_REQUIRED','HTTP 401 alone must not be labeled a provider login requirement');
  assert.equal(classifyWatchFailure({source:'HTTP',status:404}).code,'HTTP_NOT_FOUND');
  assert.notEqual(classifyWatchFailure({source:'HTTP',status:404}).code,'LINK_EXPIRED','HTTP 404 alone must not be labeled an expired link');
  assert.equal(classifyWatchFailure({source:'PROVIDER',condition:'REGION_RESTRICTED'}).code,'REGION_RESTRICTED');
  assert.equal(classifyWatchFailure({source:'PROVIDER',condition:'LOGIN_REQUIRED'}).code,'LOGIN_REQUIRED');
  assert.equal(classifyWatchFailure({source:'PROVIDER',condition:'LINK_EXPIRED'}).code,'LINK_EXPIRED');
  assert.equal(classifyWatchFailure({source:'PROVIDER',condition:'EMBED_DISABLED'}).action,'OPEN_OFFICIAL_PAGE_IF_ELIGIBLE');
  assert.equal(classifyWatchFailure({source:'NETWORK'}).code,'NETWORK_ERROR');
  assert.equal(classifyWatchFailure({source:'LOCAL_MEDIA',condition:'FILE_MISSING'}).code,'LOCAL_MEDIA_MISSING');
  assert.equal(classifyWatchFailure({source:'LOCAL_MEDIA',condition:'MEDIA_DECODE_FAILED'}).code,'MEDIA_DECODE_FAILED');
  assert.equal(classifyWatchFailure({source:'USER',condition:'CANCELLED'}).code,'USER_CANCELLED');
  assert.equal(classifyWatchFailure({source:'PROVIDER',condition:'UNMAPPED'}).code,'UNKNOWN');
  assert.equal(classifyWatchFailure(null).code,'UNKNOWN');
  assert.equal(evaluateWatchRoute({mode:'AUTO_DOWNLOAD'}),null,'unknown routes fail closed');

  assert.equal(embed.contract,WATCH_ROUTING_CONTRACT);
  assert.equal(Object.keys(embed).sort().join(','),'contract,mode,playbackEvidence,reason,state','route decisions contain no URLs, filenames, or media identity data');
  console.log('Watch routing contract: all 5 route modes and tested permission/error boundaries PASS');
}finally{rmSync(folder,{recursive:true,force:true});}
