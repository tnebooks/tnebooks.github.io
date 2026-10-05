import hashlib,json,re
from pathlib import Path
import fitz,yaml
from pydantic import Field
from .models import Contract,BookManifest,LessonSpec,ItemInventory,LessonEvidence,Boundary
from .source import prepare_pages
from . import prompts

class ChapterMap(Contract):
    lessons: list[LessonSpec]
    excluded_sections: list[str]
    issues: list[str]

class MapCheck(Contract):
    valid: bool
    issues: list[str]

def check_inventory(result: ItemInventory, lesson: LessonSpec, medium: str) -> None:
    if result.issues: raise ValueError('Source inventory issues: '+'; '.join(result.issues))
    if result.language!=medium: raise ValueError('Source medium mismatch or unknown language')
    if not result.items or len({i.id for i in result.items})!=len(result.items): raise ValueError('Empty or duplicate source inventory')
    for item in result.items:
        if not re.fullmatch(r'[a-zA-Z0-9.-]+',item.id): raise ValueError('Unsafe source-item ID')
        if not lesson.pdf_start<=item.page<=lesson.pdf_end: raise ValueError('Source item outside lesson pages')
        if item.box is not None: Boundary(page=item.page,box=item.box)
        if item.flags: raise ValueError('Unresolved source issue: '+'; '.join(item.flags))

def discover_lessons(book: BookManifest, client, cache: Path) -> BookManifest:
    if book.lessons: return book
    with fitz.open(book.pdf) as d: bookmarks=d.get_toc()
    folders=[]
    root=book.output/f'content.{book.medium}/docs'
    for p in root.glob('*/_index.md') if root.exists() else []:
        raw=p.read_text(encoding='utf-8'); metadata=yaml.safe_load(raw.split('---',2)[1]) if raw.startswith('---') else {}
        folders.append({'slug':p.parent.name,'title':metadata.get('title'),'weight':metadata.get('weight')})
    sample=LessonSpec(id='contents',title='Contents',slug='contents',weight=1,pdf_start=1,pdf_end=min(12,book.page_count))
    pages=[p for p in prepare_pages(book,sample,cache/'pages') if 'intentional-blank-source-page' not in p.warnings]
    candidates=[]; exclusions=[]
    for offset in range(0,len(pages),client.limits.page_window):
        window=pages[offset:offset+client.limits.page_window]
        result,_=client.respond(prompts.DISCOVERY,{'medium':book.medium,'bookmarks':bookmarks,'existing_folders':folders,'previous_candidates':[x.model_dump() for x in candidates],'pages':[{'page':p.page,'text':p.text} for p in window]},[p.image for p in window],ChapterMap)
        if result.issues: raise ValueError('Chapter discovery needs a corrected manifest: '+'; '.join(result.issues))
        for lesson in result.lessons:
            prior=next((x for x in candidates if x.id==lesson.id),None)
            if prior and prior!=lesson: raise ValueError('Conflicting chapter candidates; correct manifest')
            if not prior: candidates.append(lesson)
        exclusions.extend(result.excluded_sections)
    if not candidates: raise ValueError('No verified lessons found; provide a chapter manifest')
    mapped=BookManifest.model_validate({**book.model_dump(),'lessons':candidates,'excluded_sections':list(dict.fromkeys(exclusions))})
    for lesson in mapped.lessons:
        for n in sorted({lesson.pdf_start,lesson.pdf_end}):
            one=lesson.model_copy(update={'pdf_start':n,'pdf_end':n,'boundaries':[b for b in lesson.boundaries if b.page==n]})
            page=list(prepare_pages(mapped,one,cache/'pages'))[0]
            check,_=client.respond(prompts.BOUNDARIES,{'lesson':lesson.model_dump(),'boundary_page':n,'text':page.text},[page.image],MapCheck)
            if not check.valid or check.issues: raise ValueError('Chapter boundary review failed; correct manifest')
    return mapped

def inventory_lesson(book: BookManifest, lesson: LessonSpec, client, cache: Path) -> LessonEvidence:
    pages=list(prepare_pages(book,lesson,cache/'pages')); items=[]
    window_size=getattr(getattr(client,'limits',None),'page_window',2)
    for offset in range(0,len(pages),window_size):
        window=[p for p in pages[offset:offset+window_size] if 'intentional-blank-source-page' not in p.warnings]
        if not window: continue
        key=hashlib.sha256(json.dumps([book.pdf_sha256,[[p.checksum,p.text,p.warnings] for p in window],book.medium,client.model,prompts.VERSION,lesson.model_dump()],sort_keys=True).encode()).hexdigest()
        dest=cache/'inventories'/f'{key}.json'; dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists() and not getattr(client,'force',False): result=ItemInventory.model_validate_json(dest.read_text(encoding='utf-8'))
        else:
            result,_=client.respond(prompts.INVENTORY,{'medium':book.medium,'lesson':lesson.model_dump(),'pages':[{'page':p.page,'text':p.text,'warnings':p.warnings} for p in window]},[p.image for p in window],ItemInventory)
            check_inventory(result,lesson,book.medium)
            dest.write_text(result.model_dump_json(indent=2),encoding='utf-8')
        check_inventory(result,lesson,book.medium)
        if any(not window[0].page<=i.page<=window[-1].page for i in result.items): raise ValueError('Item outside supplied source window')
        if {p.page for p in window}!={i.page for i in result.items}: raise ValueError('Inventory omitted a source page')
        items.extend(result.items)
    check_inventory(ItemInventory(items=items,language=book.medium,issues=[]),lesson,book.medium)
    fingerprint=hashlib.sha256(json.dumps([i.model_dump() for i in items],sort_keys=True).encode()).hexdigest()
    return LessonEvidence(lesson=lesson,medium=book.medium,pages=pages,items=sorted(items,key=lambda i:(i.page,i.order)),fingerprint=fingerprint)
