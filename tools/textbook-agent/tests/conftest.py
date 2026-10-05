from pathlib import Path
import fitz
import pytest

@pytest.fixture
def pdf(tmp_path):
    p=tmp_path/'book.pdf'
    d=fitz.open()
    for text in ['Unit 1 Motion\nForce is a push or pull.','Unit 2 Plants\nLeaves make food.']:
        page=d.new_page(width=400,height=400)
        page.insert_text((30,40),text)
        page.draw_rect(fitz.Rect(40,100,160,180),color=(0,0,0))
    d.save(p); d.close()
    return p

@pytest.fixture
def book(pdf,tmp_path):
    from textbook_agent.models import BookManifest, LessonSpec
    return BookManifest(book_id='science-ta',pdf=pdf,output=tmp_path/'out',medium='ta',class_name='10',subject='science',edition='2024',model='test-model',lessons=[LessonSpec(id='1',title='Motion',slug='laws-of-motion',weight=1,pdf_start=1,pdf_end=1)],page_count=2)
