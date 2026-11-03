"""Read-only Cinema projection from pinned public Match Library snapshots.

No database, personal files, media bytes, or network are accessed. A recorded
source identity is not evidence of current playback or media distribution rights.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

HERE = Path(__file__).resolve().parent
INPUTS = (
    ('generated/goal15-main-fan-universe-public-v0.2/match-library-strict-public.json', '1e038dcab1a39c6c37d7687a066cd391328681a89950ae02e937ab1a0ac65930'),
    ('generated/goal17-1-real-content-v0.1/public/official-match-video-additions.json', '6f05d1fc48fb74ffc305abe20fd9152973bd96bb009fe6a183d42c031a31198a'),
    ('generated/goal27-match-experience-v0.1/public/match-experience-delta-v0.1.json', '05922e4bb8ae3e8ddbe392485f386d28feb025c48ff83d9bd73aca0bd3ec94e3'),
)

def load_inputs():
    result=[]
    for relative, expected in INPUTS:
        # Git normalizes these text snapshots to LF; accept Windows checkout CRLF
        # only, never whitespace or JSON semantic changes.
        raw=(HERE/relative).read_bytes().replace(b'\r\n',b'\n')
        if hashlib.sha256(raw).hexdigest()!=expected: raise ValueError('INPUT_SHA_MISMATCH')
        result.append(json.loads(raw))
    return result

def watch_url(source):
    platform=source.get('platform',source.get('provider')); video=source.get('video_id',source.get('provider_video_id')); url=source.get('official_url',source.get('watch_url'))
    if platform!='YOUTUBE' or not isinstance(video,str) or not re.fullmatch(r'[A-Za-z0-9_-]{11}',video) or not isinstance(url,str): return None
    parsed=urlsplit(url); query=parse_qs(parsed.query,keep_blank_values=True)
    if parsed.scheme!='https' or parsed.netloc!='www.youtube.com' or parsed.path!='/watch' or parsed.fragment or query!={'v':[video]}: return None
    rights=source.get('rights',{})
    permitted=rights.get('public_listing')=='ALLOWED' and rights.get('external_viewing')=='ALLOWED'
    permitted=permitted or source.get('watch_route')=='OFFICIAL_EXTERNAL_LINK_ONLY'
    return url if permitted else None

def project(inputs):
    if len(inputs)!=3: raise ValueError('INPUT_COUNT')
    base, g17, g27=inputs
    if base.get('contract_version')!='ptti.match-library-index/0.1' or base.get('view')!='STRICT_PUBLIC': raise ValueError('BASE_CONTRACT')
    if g17.get('contract_version')!='ptti.goal17.1-match-video-additions/0.1' or g27.get('contract_version')!='ptti.main.match-experience-delta/0.1': raise ValueError('DELTA_CONTRACT')
    if g17.get('view')!='STRICT_PUBLIC_EXTERNAL_LINK_DELTA' or g27.get('view')!='STRICT_PUBLIC_EXTERNAL_LINK_DELTA': raise ValueError('DELTA_VIEW')
    if g17.get('base_goal15_library_sha256')!=INPUTS[0][1] or g27.get('base_catalog_sha256')!=INPUTS[0][1]: raise ValueError('BASE_IDENTITY')
    matches=[]; sources=[]; match_ids=set(); source_ids=set(); urls=set()
    for package in inputs:
        is17=package is g17
        for row in package['matches']:
            mid=row.get('match_id')
            if not isinstance(mid,str) or not mid or mid in match_ids: raise ValueError('DUPLICATE_MATCH')
            match_ids.add(mid)
            event=row.get('event') if isinstance(row.get('event'),dict) else {'name':row.get('event_name'),'event_id':row.get('event_id'),'date':row.get('match_date'),'year':row.get('event_year')}
            matches.append({'match_id':mid,'event':event,'match_type':row.get('match_type',row.get('category','UNKNOWN')),'round':row.get('round') or 'UNKNOWN','participants':row.get('participants',[]),'identity_status':row.get('identity_status','UNKNOWN'),'source_ids':row.get('video_source_ids',[]),'evidence_source_ids':row.get('evidence_source_ids',[row['identity_evidence_source_id']] if row.get('identity_evidence_source_id') else []),'media_sha256':None,'media_sha256_status':'UNKNOWN'})
        for row in package['video_sources']:
            sid=row.get('source_id'); url=watch_url(row)
            if not sid or sid in source_ids: raise ValueError('DUPLICATE_SOURCE')
            source_ids.add(sid)
            if not url: raise ValueError('SOURCE_NOT_ELIGIBLE')
            if url in urls: raise ValueError('DUPLICATE_URL')
            urls.add(url)
            linked=row.get('match_id') if is17 else row.get('canonical_match_id')
            sources.append({'source_id':sid,'match_id':linked,'video_id':row.get('video_id',row.get('provider_video_id')),'provider':'YOUTUBE','official_url':url,'title':row.get('original_title') or row.get('title'),'publisher':row.get('publisher'),'identity_status':row.get('source_identity_status',row.get('publisher_status','UNKNOWN')),'content_type_claim':row.get('content_type_claim','FULL_MATCH_TITLE_CLAIM' if is17 else 'UNKNOWN'),'evidence_source_ids':row.get('rights',{}).get('evidence_source_ids',[sid] if is17 else []),'evidence_url':url,'external_navigation':'ALLOWED_AS_RECORDED','embedding':'UNKNOWN','download':'NOT_GRANTED','redistribution':'NOT_GRANTED','media_sha256':None,'media_sha256_status':'UNKNOWN','page_status':'NOT_TESTED','playback_status':'NOT_TESTED','current_session_eligibility':'NOT_EVALUATED_CURRENT_SESSION'})
    by_source={s['source_id']:s for s in sources}
    for match in matches:
        for sid in match['source_ids']:
            if sid not in by_source or by_source[sid]['match_id']!=match['match_id']: raise ValueError('MATCH_SOURCE_MISMATCH')
    for source in sources:
        if source['match_id'] is not None and (source['match_id'] not in match_ids or source['source_id'] not in next(m['source_ids'] for m in matches if m['match_id']==source['match_id'])): raise ValueError('SOURCE_MATCH_MISMATCH')
    return {'contract_version':'ptti.cinema-match-projection/0.1','audience':'STRICT_PUBLIC_METADATA_EXTERNAL_LINK_ONLY','input_sha256':[digest for _,digest in INPUTS], 'matches':matches,'video_sources':sources,'evidence_sources':base['evidence_sources']+g27['evidence_sources'],'notice':'Recorded metadata is not live playback, embed, media ownership or verification of authenticity. No media bytes or private paths are included.'}

def main():
    payload=project(load_inputs())
    if len(sys.argv)>1:
        match=next((m for m in payload['matches'] if m['match_id']==sys.argv[1]),None)
        if match is None: raise SystemExit('MATCH_NOT_FOUND')
        payload={'contract_version':payload['contract_version'],'match':match,'video_sources':[s for s in payload['video_sources'] if s['match_id']==match['match_id']],'evidence_sources':[e for e in payload['evidence_sources'] if e['source_id'] in match['evidence_source_ids']]}
    sys.stdout.buffer.write((json.dumps(payload,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf-8'))

if __name__=='__main__': main()
