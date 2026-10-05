from textbook_agent.pipeline import run_book
from textbook_agent.models import RunLimits,ItemInventory,LessonDraft,SectionEdit,ReviewResult,SourceItem
from textbook_agent.paths import lesson_path

class FixtureClient:
    def __init__(self,model,limits,on_usage=None): self.model=model; self.limits=limits; self.calls=0; self.lesson_calls=0; self.usage=[]; self.unknown_requests=0
    def respond(self,task,payload,images,schema):
        self.calls+=1
        if schema is ItemInventory:
            return ItemInventory(items=[SourceItem(id='p1',kind='prose',page=1,box=None,text='Force is a push or pull.',caption='',exercise_id=None,order=1,flags=[])],language='ta',issues=[]),None
        if schema is LessonDraft:
            if 'study aids' in task.lower(): return LessonDraft(edits=[],assets=[],aids=[],notes=[]),None
            current=payload['existing_sections']; old=current[0] if current else None
            return LessonDraft(edits=[SectionEdit(anchor=payload['target_anchor'],expected_sha256=old['sha256'] if old else None,markdown='## Force\n\nForce is a push or pull.\n\n',after_anchor=None,item_ids=['p1'])],assets=[],aids=[],notes=[]),None
        if schema is ReviewResult: return ReviewResult(covered_ids=['p1'],findings=[],verified_aid_ids=[]),None
        raise AssertionError(schema)

def test_create_and_unchanged_repeat_uses_no_model_calls(book):
    created=[]
    def factory(*args,**kwargs):
        c=FixtureClient(*args,**kwargs); created.append(c); return c
    first=run_book(book,RunLimits(),'run',client_factory=factory)
    assert first.lessons['1']['status']=='applied'
    assert 'push or pull' in lesson_path(book,book.lessons[0]).read_text()
    second=run_book(book,RunLimits(),'run',client_factory=factory)
    assert second.lessons['1']['status']=='unchanged' and len(created)==1

def test_audit_does_not_write_lesson(book):
    result=run_book(book,RunLimits(),'audit',client_factory=FixtureClient)
    assert result.lessons['1']['status']=='needs-review'
    assert not lesson_path(book,book.lessons[0]).exists()

def test_missing_key_leaves_no_placeholder_lesson(book,monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    result=run_book(book,RunLimits(),'run')
    assert result.status=='interrupted'
    assert not lesson_path(book,book.lessons[0]).exists()

def test_resume_preserves_selected_lesson_scope(book):
    from textbook_agent.models import LessonSpec
    second=LessonSpec(id='2',title='Plants',slug='plants',weight=2,pdf_start=2,pdf_end=2)
    book=book.model_copy(update={'lessons':book.lessons+[second]})
    first=run_book(book,RunLimits(),'run',selected_ids={'1'},client_factory=FixtureClient)
    resumed=run_book(book,RunLimits(),'run',run_id=first.id,client_factory=FixtureClient)
    assert set(resumed.lessons)=={'1'}

def test_english_routes_into_content_en(book):
    class EnglishClient(FixtureClient):
        def respond(self,*args):
            result,usage=super().respond(*args)
            if isinstance(result,ItemInventory): result.language='en'
            return result,usage
    book=book.model_copy(update={'medium':'en','book_id':'science-en'})
    result=run_book(book,RunLimits(),'run',client_factory=EnglishClient)
    assert result.status=='complete'
    assert (book.output/'content.en/docs/laws-of-motion/_index.md').is_file()
    assert not (book.output/'content.ta').exists()

def test_failed_review_repairs_at_most_twice(book):
    class FailedReview(FixtureClient):
        repairs=0
        def respond(self,task,payload,images,schema):
            if schema is ReviewResult: return ReviewResult(covered_ids=[],findings=[],verified_aid_ids=[]),None
            if 'findings' in payload:
                self.repairs+=1; old=payload['existing_sections'][0]
                return LessonDraft(edits=[SectionEdit(anchor=old['anchor'],expected_sha256=old['sha256'],markdown='## Force\n\nForce is a push or pull.',after_anchor=None,item_ids=['p1'])],assets=[],aids=[],notes=[]),None
            return super().respond(task,payload,images,schema)
    clients=[]
    def factory(*args,**kwargs):
        c=FailedReview(*args,**kwargs); clients.append(c); return c
    state=run_book(book,RunLimits(),'run',client_factory=factory)
    assert state.status=='needs-review' and clients[0].repairs==2
    assert not lesson_path(book,book.lessons[0]).exists()
