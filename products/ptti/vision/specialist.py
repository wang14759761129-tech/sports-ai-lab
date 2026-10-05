"""CPU-only evidence and leakage guards for model-level experiments."""
import hashlib
import json
from pathlib import Path

OFFICIAL_SHA='00d707b9db7a49561c411e4765956e79bcd7c7e20c7a0a535073440b3e972342'

def sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        while chunk:=f.read(1024*1024):h.update(chunk)
    return h.hexdigest()

def validate_split(manifest):
    roles=['train','dev','known_evaluation','final_test']
    matches={}
    for role in roles:
        samples=manifest[role]
        if len(samples)!=len(set(samples)):raise ValueError('Duplicate source ID')
        if any(len(s.split('/'))!=3 or not s.startswith('tabletennis/') for s in samples):raise ValueError('Invalid source ID')
        matches[role]={s.split('/')[1] for s in samples}
    for i,a in enumerate(roles):
        for b in roles[i+1:]:
            if matches[a]&matches[b]:raise ValueError('Match-level leakage: '+a+' / '+b)
    if not manifest['train'] or not manifest['dev']:raise ValueError('Missing train/dev split')
    return matches

def validate_model(path,expected_sha):
    if len(expected_sha)!=64 or sha256(path)!=expected_sha:raise ValueError('Checkpoint SHA256 mismatch')

def validate_provenance(record,checkpoint):
    required=['parent_checkpoint_sha256','split_sha256','config_sha256','epochs','optimizer','learning_rate','seed',
              'best_epoch','validation_metric','checkpoint_sha256','tti_commit','racketvision_commit','gpu','torch','cuda','train_match_ids','dev_match_ids']
    if any(k not in record for k in required):raise ValueError('Incomplete checkpoint provenance')
    if set(record['train_match_ids'])&set(record['dev_match_ids']):raise ValueError('Provenance match leakage')
    if not 1<=record['best_epoch']<=record['epochs']:raise ValueError('Invalid best epoch')
    if record['parent_checkpoint_sha256']!=OFFICIAL_SHA:raise ValueError('Wrong parent checkpoint')
    validate_model(checkpoint,record['checkpoint_sha256'])

def safe_checkpoint_target(parent,target):
    if Path(parent).resolve()==Path(target).resolve() or Path(target).exists():raise ValueError('Checkpoint overwrite forbidden')

def validate_final_test(manifest,candidate_lock):
    validate_split(manifest)
    if not candidate_lock.get('accepted_on_known_evaluation') or not candidate_lock.get('model_sha256'):
        raise ValueError('Final test requires accepted frozen candidate')
    if len({s.split('/')[1] for s in manifest['final_test']})<5:raise ValueError('At least five untouched matches required')
    if {s.split('/')[1] for s in manifest['final_test']} & set(manifest.get('parent_exposed_match_ids',[])):raise ValueError('Final test overlaps parent training/validation exposure')
    if manifest.get('final_selection_after_candidate_freeze') is not True:raise ValueError('Final test selection was premature')
