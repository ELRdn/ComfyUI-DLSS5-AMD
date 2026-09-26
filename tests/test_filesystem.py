import json
import os
from pathlib import Path
import pytest
from amd_nr.errors import ContractError, ResourceError
from amd_nr.filesystem import (read_json, write_json, sha256_file, sha256_bytes,
                               workspace_lock, publish_new_file, check_disk)

@pytest.mark.parametrize('text', ['{', '[]', '{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}', 'null'])
def test_invalid_json(tmp_path, text):
    path = tmp_path/'bad.json'; path.write_text(text)
    with pytest.raises(ContractError):
        read_json(path)

def test_json_size_limit(tmp_path):
    path = tmp_path/'large.json'; path.write_text('{"x":"long"}')
    with pytest.raises(ContractError):
        read_json(path, limit=3)

def test_json_unicode_and_bom(tmp_path):
    path = tmp_path/'日本語.json'
    write_json(path, {'message':'ひろなお', 'value':1})
    assert read_json(path)['message'] == 'ひろなお'
    path.write_text('\ufeff{"x":2}', encoding='utf-8')
    assert read_json(path) == {'x':2}

def test_atomic_existing_output_never_overwritten(tmp_path):
    source, dest = tmp_path/'s', tmp_path/'d'
    source.write_bytes(b'new'); dest.write_bytes(b'ORIGINAL')
    with pytest.raises(FileExistsError):
        publish_new_file(source,dest)
    assert dest.read_bytes() == b'ORIGINAL'
    assert not list(tmp_path.glob('.amd-nr-publish-*'))

def test_atomic_publish_and_hash(tmp_path):
    source, dest = tmp_path/'s', tmp_path/'other'/'日本語 file.png'
    source.write_bytes(b'payload')
    publish_new_file(source,dest)
    assert sha256_file(dest) == sha256_bytes(b'payload')

def test_publish_copy_failure_leaves_no_final(tmp_path, monkeypatch):
    import amd_nr.filesystem as fs
    source, dest = tmp_path/'s', tmp_path/'d'; source.write_bytes(b'payload')
    def fail(*args,**kwargs): raise OSError('simulated disk error')
    monkeypatch.setattr(fs.shutil,'copyfileobj',fail)
    with pytest.raises(ResourceError): publish_new_file(source,dest)
    assert not dest.exists()
    assert not list(tmp_path.glob('.amd-nr-publish-*'))

def test_workspace_lock_releases_on_exception(tmp_path):
    with pytest.raises(ValueError):
        with workspace_lock(tmp_path):
            with pytest.raises(ResourceError):
                with workspace_lock(tmp_path): pass
            raise ValueError('intentional')
    with workspace_lock(tmp_path): pass

def test_low_disk_rejected(tmp_path):
    with pytest.raises(ResourceError): check_disk(tmp_path, 10**30, 0)

def test_symlink_report_rejected(tmp_path):
    target=tmp_path/'target'; target.write_text('{}')
    link=tmp_path/'link'
    try: link.symlink_to(target)
    except OSError: pytest.skip('symlink permission unavailable')
    with pytest.raises(ContractError): read_json(link)

def test_symlink_destination_not_followed(tmp_path):
    source=tmp_path/'s'; source.write_bytes(b'new')
    target=tmp_path/'target'; target.write_bytes(b'old')
    link=tmp_path/'link'
    try: link.symlink_to(target)
    except OSError: pytest.skip('symlink permission unavailable')
    with pytest.raises(FileExistsError): publish_new_file(source,link)
    assert target.read_bytes()==b'old'
