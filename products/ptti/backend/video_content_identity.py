"""Read-only full content verification for user-requested Moment boundaries."""
import hashlib
import os
import re
from pathlib import Path


def verify_registered_content(row, *, on_block=None):
    expected = row.get('source_sha256')
    if row.get('hash_status') != 'VERIFIED' or not isinstance(expected, str) or not re.fullmatch(r'[0-9a-fA-F]{64}', expected):
        raise ValueError('视频登记身份不可验证')
    path = Path(row['original_path'])
    def signature(st):
        return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns)
    try:
        with path.open('rb') as stream:
            before = os.fstat(stream.fileno())
            if before.st_size != row['file_size'] or before.st_mtime_ns != row['mtime_ns'] or before.st_ino != row['file_id']:
                raise ValueError('文件已改变，请重新关联')
            if signature(path.stat()) != signature(before):
                raise ValueError('文件身份已改变')
            digest = hashlib.sha256()
            while block := stream.read(1024 * 1024):
                digest.update(block)
                if on_block is not None:
                    on_block()
            after = os.fstat(stream.fileno())
            if signature(before) != signature(after) or signature(path.stat()) != signature(after):
                raise ValueError('校验期间文件发生变化')
            if digest.hexdigest() != expected.lower():
                raise ValueError('文件内容与登记身份不一致')
    except OSError as exc:
        raise ValueError('文件无法读取或已不存在') from exc
    return expected.lower()
