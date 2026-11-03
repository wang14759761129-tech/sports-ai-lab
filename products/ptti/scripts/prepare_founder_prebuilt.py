"""Prepare previously verified frontend assets without invoking npm or a build."""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

WEB = '5946c0c4d0517ade316b748933151816c6c504d3'
HOST = 'e6e45aa6175016832fcebfc46aed8c8bcb2a4cc9'
PINNED_MANIFEST = 'd3520768318fa15f0e38ea513053a0928a27d04aca84f6ae76041102ff3d7dd8'
ROOT = Path(__file__).resolve().parents[3]

def sha(data):
    return hashlib.sha256(data).hexdigest()

def verify_manifest(data, source, pinned_manifest=PINNED_MANIFEST):
    if sha(data) != pinned_manifest:
        raise ValueError('Original manifest SHA-256 differs from reviewed manifest')
    expected = {}
    for line in data.decode('utf-8-sig').splitlines():
        match = re.fullmatch(r'([0-9a-f]{64})[ \t]+(.+)', line)
        if not match:
            raise ValueError('Malformed manifest entry')
        name = match.group(2).replace('\\', '/')
        parts = name.split('/')
        if any(p in ('', '.', '..') or ':' in p for p in parts) or name in expected:
            raise ValueError('Invalid or duplicate manifest path')
        expected[name] = match.group(1)
    if len(expected) != 10 or not {'index.html', 'demo-synthetic.mp4'} <= expected.keys():
        raise ValueError('Unexpected manifest contents')
    root = source.resolve(strict=True)
    actual = {}
    for p in root.rglob('*'):
        if p.is_symlink() or (hasattr(p, 'is_junction') and p.is_junction()):
            raise ValueError('Links and junctions in assets are not accepted')
        if p.is_file():
            actual[p.relative_to(root).as_posix()] = sha(p.read_bytes())
    if actual != expected:
        raise ValueError('Source asset set or content differs from reviewed manifest')
    return expected

def prepare(source, manifest, output, web_worktree, host_commit, pinned_manifest=PINNED_MANIFEST):
    if host_commit != HOST:
        raise ValueError('Unreviewed host identity')
    if output.exists() or output.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError('Output must be new and outside the host worktree')
    head = subprocess.check_output(['git', '-C', str(web_worktree), 'rev-parse', 'HEAD'], text=True).strip()
    if head != WEB or subprocess.check_output(['git', '-C', str(web_worktree), 'status', '--porcelain'], text=True).strip():
        raise ValueError('Web source must be the clean fixed commit')
    data = manifest.read_bytes()
    files = verify_manifest(data, source, pinned_manifest)
    # Prior build reported unified mode and this source commit; the pinned hashes
    # bind this handoff to that recorded artifact, not to an embedded Git signature.
    output.mkdir(parents=True)
    try:
        shutil.copytree(source, output / 'dist')
        verify_manifest(data, output / 'dist', pinned_manifest)
        info = {'schema':'ptti.founder.dist/1', 'source_commit':WEB,
                'host_commit':HOST, 'unified_mode':True, 'files':files,
                'provenance':{'basis':'previously reported unified build and pinned artifact manifest',
                              'original_manifest_sha256':sha(data),
                              'embedded_git_attestation':False}}
        (output / 'founder-build.json').write_text(json.dumps(info,indent=2)+'\n',encoding='utf-8')
        from importlib.util import spec_from_file_location, module_from_spec
        spec = spec_from_file_location('founder_guard', ROOT/'products/ptti/apps/founder_preview_guard.py')
        guard = module_from_spec(spec); spec.loader.exec_module(guard)
        guard.verify_dist(output/'dist', output/'founder-build.json')
    except BaseException:
        shutil.rmtree(output)
        raise

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dist',required=True,type=Path);p.add_argument('--manifest',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path);p.add_argument('--web-worktree',required=True,type=Path)
    p.add_argument('--host-commit',required=True)
    args=p.parse_args();prepare(args.dist,args.manifest,args.output,args.web_worktree,args.host_commit)
    print('Verified prebuilt assets; no build invoked:',args.output)
if __name__ == '__main__':main()
