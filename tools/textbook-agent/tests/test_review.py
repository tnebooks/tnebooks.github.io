from pathlib import Path
from textbook_agent.models import LessonEvidence,SourceItem,SourcePage,ReviewResult,Finding
from textbook_agent.review import review_lesson

def test_model_claim_does_not_hide_missing_coverage(book,tmp_path):
    page=SourcePage(page=1,width=400,height=400,text='force',image=tmp_path/'p.png',checksum='x')
    item=SourceItem(id='p1',kind='prose',page=1,box=None,text='Force',caption='',exercise_id=None,order=1,flags=[])
    evidence=LessonEvidence(lesson=book.lessons[0],medium='ta',pages=[page],items=[item],fingerprint='x')
    class Client:
        def respond(self,*args): return ReviewResult(covered_ids=[],findings=[],verified_aid_ids=[],teacher_approved=True),None
    result=review_lesson(evidence,'## Force\n\nMissing.',[],Client())
    assert any(f.blocking and f.item_id=='p1' for f in result.findings)
    assert result.teacher_approved is False

def test_safe_arithmetic_rejects_code():
    import pytest
    from textbook_agent.review import numeric_value
    assert numeric_value('2 * (3 + 4)')==14
    with pytest.raises(ValueError): numeric_value("__import__('os').system('echo bad')")

def test_figure_review_sees_actual_crop(book,tmp_path):
    from textbook_agent.models import AssetRecord
    page=SourcePage(page=1,width=400,height=400,text='figure',image=tmp_path/'p.png',checksum='x')
    item=SourceItem(id='p1',kind='figure',page=1,box=[0,0,.5,.5],text='',caption='Figure',exercise_id=None,order=1,flags=[])
    evidence=LessonEvidence(lesson=book.lessons[0],medium='ta',pages=[page],items=[item],fingerprint='x')
    asset=AssetRecord(item_id='p1',page=1,box=[0,0,.5,.5],caption='Figure',path='crop.png',sha256='x',width=100,height=100,local_file=tmp_path/'crop.png')
    class Client:
        calls=0
        def respond(self,task,payload,images,schema):
            self.calls+=1
            if self.calls==2: assert images==[page.image,asset.local_file]
            return ReviewResult(covered_ids=['p1'],findings=[],verified_aid_ids=[]),None
    c=Client(); review_lesson(evidence,'Figure', [asset],c)
    assert c.calls==2
