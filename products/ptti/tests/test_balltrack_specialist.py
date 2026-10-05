from pathlib import Path
import pytest
from vision.specialist import validate_split,validate_model,validate_provenance,safe_checkpoint_target,sha256,validate_final_test

def split():
    return {'train':['tabletennis/match20/001'],'dev':['tabletennis/match28/000'],'known_evaluation':['tabletennis/match10/001'],'final_test':[], 'parent_exposed_match_ids':['match20','match28','match10']}

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

def test_final_test_rejects_parent_exposed_matches():
    m=split();m['final_test']=[f'tabletennis/match{i}/000' for i in range(40,45)];m['parent_exposed_match_ids'].append('match40');m['final_selection_after_candidate_freeze']=True
    with pytest.raises(ValueError):validate_final_test(m,{'model_sha256':'a'*64,'accepted_on_known_evaluation':True})

def test_valid_provenance_binds_checkpoint_content(tmp_path):
    from vision.specialist import OFFICIAL_SHA
    checkpoint=tmp_path/'model.pth';checkpoint.write_bytes(b'fake fixture, not a trained model')
    record={k:'fixture' for k in ['split_sha256','config_sha256','optimizer','tti_commit','racketvision_commit','gpu','torch','cuda']}
    record.update(parent_checkpoint_sha256=OFFICIAL_SHA,epochs=3,learning_rate=1e-5,seed=20261005,best_epoch=1,validation_metric={'f1':.1},checkpoint_sha256=sha256(checkpoint),train_match_ids=['train'],dev_match_ids=['dev'])
    validate_provenance(record,checkpoint)
    checkpoint.write_bytes(b'changed')
    with pytest.raises(ValueError):validate_provenance(record,checkpoint)
