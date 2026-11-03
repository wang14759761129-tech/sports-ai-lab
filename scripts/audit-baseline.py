"""Conservative local pattern and file-boundary audit; not a full secret certification."""
import ast
import hashlib
import json
import os
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
os.environ['GIT_OPTIONAL_LOCKS'] = '0'
def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args]).decode('utf-8').splitlines()

secret = re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[A-Z0-9]{16}|sk-(?:proj-)?[A-Za-z0-9_-]{24,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
assignment = re.compile(rb'(?i)(?:api[_-]?key|access[_-]?token|client[_-]?secret|password|passwd)\s*[=:]\s*[\x22\x27][^\x22\x27\r\n]{8,}[\x22\x27]')
personal = re.compile(rb'(?i)(?:[A-Z]:[\\/]+Users[\\/]+|[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})')
denied = re.compile(r'(?i)(\.(exe|dll|zip|7z|mp4|mkv|mov|db|sqlite|sqlite3|webp|jpg|jpeg|png)$|(^|/)(internal-review|reviewed-originals|node_modules|dist|\.env[^/]*)(/|$))')
names = sorted(set(git('ls-files') + git('ls-files', '--others', '--exclude-standard')))
issues, files, python_count = [], [], 0
for name in names:
    path = ROOT / name
    if path.is_symlink() or bool(getattr(path.lstat(), 'st_file_attributes', 0) & 1024):
        issues.append({'path': name, 'reason': 'symlink-or-reparse'}); continue
    if not path.is_file():
        issues.append({'path': name, 'reason': 'missing'}); continue
    data = path.read_bytes()
    if denied.search(name) or secret.search(data) or assignment.search(data) or personal.search(data) or b'\0' in data:
        issues.append({'path': name, 'reason': 'file-or-sensitive-pattern'})
    try:
        data.decode('utf-8', errors='strict')
        if path.suffix == '.py': ast.parse(data.decode('utf-8-sig')); python_count += 1
    except (UnicodeDecodeError, SyntaxError): issues.append({'path': name, 'reason': 'encoding-or-python-syntax'})
    files.append({'path': name, 'sha256': hashlib.sha256(data).hexdigest()})
result = {'status': 'FAIL' if issues else 'PASS_PATTERN_SCOPE_ONLY', 'files': len(files), 'python_ast_pass': python_count, 'issues': issues, 'limitations': ['No professional secret scanner installed', 'No semantic certification of arbitrary personal data', 'Ignored dependency binaries and build outputs are not upload candidates'], 'file_hashes': files}
(ROOT / '.qa').mkdir(exist_ok=True)
(ROOT / '.qa/security-scan.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k != 'file_hashes'}))
raise SystemExit(1 if issues else 0)
