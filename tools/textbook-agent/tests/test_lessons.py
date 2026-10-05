from pathlib import Path
import pytest
from textbook_agent.lessons import read_existing, assemble_lesson, section_hash
from textbook_agent.models import LessonDraft,SectionEdit

def test_targeted_repair_preserves_front_matter_and_supplement(book,tmp_path):
    p=tmp_path/'_index.md'; front='---\ntitle: Motion\nweight: 1\nreferences:\n  videos: ["youtube:123"]\n---\n'
    p.write_text(front+'\n## Force\n\nIncorrect.\n\n## Extra\n\nTeacher notes and video.\n')
    existing=read_existing(p); anchor=next(k for k,v in existing.sections.items() if 'Incorrect' in v)
    draft=LessonDraft(edits=[SectionEdit(anchor=anchor,expected_sha256=section_hash(existing.sections[anchor]),markdown='## Force\n\nForce is a push or pull.\n\n',after_anchor=None,item_ids=['p1-prose-1'])],assets=[],aids=[],notes=[])
    output=assemble_lesson(book.lessons[0],existing,draft,[])
    assert output.startswith(front) and 'Teacher notes and video.' in output and 'Incorrect' not in output
    draft.edits[0].expected_sha256='wrong'
    with pytest.raises(ValueError): assemble_lesson(book.lessons[0],existing,draft,[])

def test_new_lesson_and_unbound_asset(book):
    draft=LessonDraft(edits=[SectionEdit(anchor='new-1',expected_sha256=None,markdown='## Force\n\nForce.',after_anchor=None,item_ids=['p1'])],assets=[],aids=[],notes=[])
    assert 'weight: 1' in assemble_lesson(book.lessons[0],None,draft,[])
    draft.edits[0].markdown+=' {{asset:missing}}'
    with pytest.raises(ValueError): assemble_lesson(book.lessons[0],None,draft,[])

def test_source_and_aid_markers_support_focused_review(book):
    from textbook_agent.models import StudyAid
    draft=LessonDraft(edits=[SectionEdit(anchor='new-1',expected_sha256=None,markdown='## Force\n\nForce.',after_anchor=None,item_ids=['p1'])],assets=[],aids=[StudyAid(id='summary',markdown='## Study aid\n\nForce.',source_item_ids=['p1'])],notes=[])
    output=assemble_lesson(book.lessons[0],None,draft,[])
    assert 'textbook-items: ["p1"]' in output and 'textbook-aid:summary' in output
