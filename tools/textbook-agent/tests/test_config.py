import pytest
from textbook_agent.models import LessonSpec, Boundary, BookManifest
from textbook_agent.paths import lesson_path, checked_path

def test_routing(book):
    assert lesson_path(book,book.lessons[0]).relative_to(book.output).as_posix()=='content.ta/docs/laws-of-motion/_index.md'
    en=book.model_copy(update={'medium':'en'})
    assert 'content.en' in str(lesson_path(en,en.lessons[0]))

@pytest.mark.parametrize('changes',[{'pdf_start':0},{'pdf_start':2,'pdf_end':1},{'slug':'../escape'}])
def test_invalid_lessons(changes):
    with pytest.raises(ValueError): LessonSpec.model_validate({**dict(id='1',title='Motion',slug='motion',weight=1,pdf_start=1,pdf_end=1),**changes})

def test_duplicate_and_overlapping_lessons(book):
    data=book.model_dump(); data['lessons']*=2
    with pytest.raises(ValueError): BookManifest.model_validate(data)
    b=LessonSpec(id='2',title='Next',slug='next',weight=2,pdf_start=1,pdf_end=2)
    with pytest.raises(ValueError): BookManifest.model_validate({**book.model_dump(),'lessons':[book.lessons[0],b]})

def test_shared_page_with_disjoint_boxes(book):
    a=book.lessons[0].model_copy(update={'boundaries':[Boundary(page=1,box=[0,0,1,.5])]})
    b=LessonSpec(id='2',title='Next',slug='next',weight=2,pdf_start=1,pdf_end=2,boundaries=[Boundary(page=1,box=[0,.5,1,1])],printed_pages=['iv','1'])
    result=BookManifest.model_validate({**book.model_dump(),'lessons':[a,b]})
    assert result.lessons[1].printed_pages==['iv','1']

def test_unsafe_paths(tmp_path):
    with pytest.raises(ValueError): checked_path(tmp_path,'../escape')
    with pytest.raises(ValueError): checked_path(tmp_path,'/absolute')
    (tmp_path/'link').symlink_to('/private/tmp')
    with pytest.raises(ValueError): checked_path(tmp_path,'link/escape')
