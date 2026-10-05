from pathlib import Path
import pytest
from vision.specialist import validate_split,validate_model,validate_provenance,safe_checkpoint_target,sha256,validate_final_test

def split():
    return {'train':['tabletennis/match20/001'],'dev':['tabletennis/match28/000'],'known_evaluation':['tabletennis/match10/001'],'final_test':[]}

def test_match_split_valid():assert validate_split(split())['train']=={'match20'}

def test_different_clips_same_match_is_leakage():
    m=split();m['dev']=['tabletennis/match20/002']
    with pytest.raises(ValueError):validate_split(m)

def test_known_data_cannot_be_final_test():
    m=split();m['final_test']=['tabletennis/match10/999']
    with pytest.raises(ValueError):validate_split(m)

def test_duplicate_sources_rejected():
    m=split();m['train']*=2
    with pytest.raises(ValueError):validate_split(m)

def test_model_sha_validation(tmp_path):
    p=tmp_path/'sample.pth';p.write_bytes(b'evidence');validate_model(p,sha256(p));p.write_bytes(b'changed')
    with pytest.raises(ValueError):validate_model(p,'0'*64)

def test_cannot_overwrite_parent_or_existing_model(tmp_path):
    p=tmp_path/'official.pth';p.write_bytes(b'parent')
    with pytest.raises(ValueError):safe_checkpoint_target(p,p)
    other=tmp_path/'model.pth';other.write_bytes(b'old')
    with pytest.raises(ValueError):safe_checkpoint_target(p,other)
    safe_checkpoint_target(p,tmp_path/'new.pth')

def test_incomplete_provenance_rejected(tmp_path):
    with pytest.raises(ValueError):validate_provenance({},tmp_path/'unknown.pth')

def test_final_manifest_requires_acceptance_and_frozen_model():
    m=split();m['final_test']=[f'tabletennis/match{i}/000' for i in range(40,45)];m['final_selection_after_candidate_freeze']=True
    with pytest.raises(ValueError):validate_final_test(m,{'model_sha256':'a'*64})
    validate_final_test(m,{'model_sha256':'a'*64,'accepted_on_known_evaluation':True})

def test_final_manifest_requires_five_matches():
    m=split();m['final_test']=['tabletennis/match40/000'];m['final_selection_after_candidate_freeze']=True
    with pytest.raises(ValueError):validate_final_test(m,{'model_sha256':'a'*64,'accepted_on_known_evaluation':True})
