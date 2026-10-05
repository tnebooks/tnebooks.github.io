import pytest
from textbook_agent.discovery import inventory_lesson, check_inventory
from textbook_agent.models import ItemInventory,SourceItem

def item(page=1):
    return SourceItem(id='p1-prose-1',kind='prose',page=page,box=None,text='Force is a push or pull.',caption='',exercise_id=None,order=1,flags=[])

def test_inventory_rejects_bad_source_claims(book):
    with pytest.raises(ValueError): check_inventory(ItemInventory(items=[item(2)],language='ta',issues=[]),book.lessons[0],book.medium)
    with pytest.raises(ValueError): check_inventory(ItemInventory(items=[item(),item()],language='ta',issues=[]),book.lessons[0],book.medium)
    with pytest.raises(ValueError): check_inventory(ItemInventory(items=[item()],language='en',issues=[]),book.lessons[0],book.medium)

def test_cached_inventory_does_not_rebill(book,tmp_path):
    class Client:
        model='test-model'
        calls=0
        def respond(self,task,payload,images,schema):
            self.calls+=1
            assert len(images)==1 and payload['pages'][0]['page']==1
            return ItemInventory(items=[item()],language='ta',issues=[]),None
    client=Client()
    evidence=inventory_lesson(book,book.lessons[0],client,tmp_path/'cache')
    assert evidence.items[0].text=='Force is a push or pull.'
    inventory_lesson(book,book.lessons[0],client,tmp_path/'cache')
    assert client.calls==1

def test_force_refreshes_source_inventory(book,tmp_path):
    class Client:
        model='test-model'
        force=False
        calls=0
        def respond(self,*args):
            self.calls+=1
            updated=item(); updated.text='Corrected transcription '+str(self.calls)
            return ItemInventory(items=[updated],language='ta',issues=[]),None
    client=Client(); cache=tmp_path/'cache'
    inventory_lesson(book,book.lessons[0],client,cache)
    client.force=True
    updated=inventory_lesson(book,book.lessons[0],client,cache)
    assert client.calls==2 and updated.items[0].text=='Corrected transcription 2'

def test_inventory_identity_includes_extracted_text(book,tmp_path,monkeypatch):
    import textbook_agent.discovery as discovery
    pages=list(discovery.prepare_pages(book,book.lessons[0],tmp_path/'pages'))
    class Client:
        model='test-model'
        calls=0
        def respond(self,task,payload,*args):
            self.calls+=1
            updated=item(); updated.text=payload['pages'][0]['text']
            return ItemInventory(items=[updated],language='ta',issues=[]),None
    monkeypatch.setattr(discovery,'prepare_pages',lambda *args:iter(pages))
    client=Client(); cache=tmp_path/'cache'
    inventory_lesson(book,book.lessons[0],client,cache)
    pages[0].text='Corrected extraction'
    updated=inventory_lesson(book,book.lessons[0],client,cache)
    assert client.calls==2 and updated.items[0].text=='Corrected extraction'
