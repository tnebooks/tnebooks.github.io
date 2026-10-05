from pathlib import Path
import pytest
from textbook_agent.source import prepare_pages, inspect_render
from textbook_agent.assets import crop_assets
from textbook_agent.models import LessonEvidence, AssetSpec

def test_pages_and_vector_crops(book,tmp_path):
    pages=list(prepare_pages(book,book.lessons[0],tmp_path/'cache'))
    assert 'push or pull' in pages[0].text
    assert inspect_render(pages[0].image)==[]
    evidence=LessonEvidence(lesson=book.lessons[0],medium='ta',pages=pages,items=[],fingerprint='x')
    spec=AssetSpec(item_id='f1',page=1,box=[.08,.22,.44,.48],caption='A rectangle')
    a=crop_assets(evidence,[spec],tmp_path/'stage')[0]
    b=crop_assets(evidence,[spec],tmp_path/'stage')[0]
    assert a.sha256==b.sha256 and a.width>100 and Path(tmp_path/'stage'/a.path).is_file()
    with pytest.raises(ValueError): crop_assets(evidence,[spec.model_copy(update={'box':[0,0,2,1]})],tmp_path/'stage')

def test_cache_and_empty_render(book,tmp_path):
    pages=list(prepare_pages(book,book.lessons[0],tmp_path/'cache'))
    stamp=pages[0].image.stat().st_mtime_ns
    assert list(prepare_pages(book,book.lessons[0],tmp_path/'cache'))[0].image.stat().st_mtime_ns==stamp
    from PIL import Image
    p=tmp_path/'blank.png'; Image.new('RGB',(50,50),'white').save(p)
    assert 'blank-render' in inspect_render(p)
