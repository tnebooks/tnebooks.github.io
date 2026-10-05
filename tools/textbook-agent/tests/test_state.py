import pytest
from textbook_agent.apply import apply_lesson,recover_transaction
from textbook_agent.state import fingerprint,book_lock
from textbook_agent.lessons import read_existing
from textbook_agent.paths import lesson_path

def test_teacher_edit_is_not_overwritten(book,tmp_path):
    p=lesson_path(book,book.lessons[0]); p.parent.mkdir(parents=True); p.write_text('old')
    expected=read_existing(p); stage=tmp_path/'stage'; stage.mkdir(); (stage/'_index.md').write_text('new')
    p.write_text('teacher edit')
    with pytest.raises(ValueError,match='conflict'): apply_lesson(book,book.lessons[0],stage,expected)
    assert p.read_text()=='teacher edit'

def test_apply_new_lesson_and_fingerprint_changes(book,tmp_path):
    stage=tmp_path/'stage'; stage.mkdir(); (stage/'_index.md').write_text('new')
    applied=apply_lesson(book,book.lessons[0],stage,None)
    assert applied[0].read_text()=='new'
    before=fingerprint(book,book.lessons[0],read_existing(applied[0]),{'version':'1'})
    applied[0].write_text('edit')
    assert fingerprint(book,book.lessons[0],read_existing(applied[0]),{'version':'1'})!=before

def test_concurrent_writer_is_blocked(tmp_path):
    with book_lock(tmp_path):
        with pytest.raises(ValueError):
            with book_lock(tmp_path): pass

def test_failed_apply_restores_original_files(book,tmp_path,monkeypatch):
    import textbook_agent.apply as apply_module
    p=lesson_path(book,book.lessons[0]); p.parent.mkdir(parents=True); p.write_text('original')
    expected=read_existing(p); stage=tmp_path/'stage'; stage.mkdir(); (stage/'_index.md').write_text('replacement'); (stage/'textbook-new.png').write_bytes(b'image')
    actual=apply_module.replace_file; calls=0
    def fail_second(source,target):
        nonlocal calls
        calls+=1
        if calls==2: raise OSError('simulated interruption')
        return actual(source,target)
    monkeypatch.setattr(apply_module,'replace_file',fail_second)
    with pytest.raises(OSError): apply_lesson(book,book.lessons[0],stage,expected)
    assert p.read_text()=='original' and not (p.parent/'textbook-new.png').exists()
