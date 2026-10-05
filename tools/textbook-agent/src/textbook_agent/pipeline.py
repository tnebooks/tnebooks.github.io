import json,time,uuid,hashlib,shutil
from pathlib import Path
from contextlib import contextmanager
from PIL import Image
from .models import RunState,LessonDraft,LessonEvidence,ReviewResult,AssetRecord,Contract
from .api import ModelClient,AgentError
from .config import sha256
from .paths import checked_path,lesson_path
from .state import atomic_json,save_state,load_state,fingerprint,book_lock
from .source import EXTRACTOR_VERSION
from .discovery import discover_lessons,inventory_lesson
from .lessons import read_existing,draft_lesson,assemble_lesson,image_refs,section_hash
from .assets import crop_assets
from .review import review_lesson,repair_sections
from .validation import validate_lesson
from .site import validate_site
from .apply import apply_lesson,recover_transaction
from .metrics import ResourceSampler
from .report import write_report
from . import prompts,__version__

class FigureMatch(Contract):
    item_id: str
    path: str
class FigureMatches(Contract):
    matches: list[FigureMatch]

class CachedClient:
    """Persist exact successful structured outputs so a resume does not repay for them."""
    def __init__(self,book,limits,root,state,factory,callback,force):
        self.model=book.model; self.limits=limits; self.root=root; self.state=state
        self.factory=factory; self.callback=callback; self.force=force; self.backend=None; self.lesson_calls=0; self.started=time.monotonic()
    def respond(self,task,payload,images,schema):
        if self.limits.max_seconds and time.monotonic()-self.started>=self.limits.max_seconds: raise AgentError('Run duration budget reached','budget')
        key=hashlib.sha256(json.dumps([self.model,task,payload,[sha256(p) for p in images],schema.model_json_schema()],sort_keys=True,default=str).encode()).hexdigest()
        path=self.root/'responses'/f'{key}.json'
        if path.exists() and not self.force: return schema.model_validate_json(path.read_text(encoding='utf-8')),None
        if self.backend is None:
            backend_limits=self.limits.model_copy()
            if backend_limits.max_seconds: backend_limits.max_seconds=max(.001,backend_limits.max_seconds-(time.monotonic()-self.started))
            self.backend=self.factory(self.model,backend_limits,on_usage=self.callback)
            self.backend.usage=list(self.state.usage)
        self.backend.lesson_calls=self.lesson_calls
        try: result,usage=self.backend.respond(task,payload,images,schema)
        finally: self.lesson_calls=getattr(self.backend,'lesson_calls',self.lesson_calls)
        atomic_json(path,result.model_dump(mode='json'))
        return result,usage

def versions(book):
    package=Path(__file__).parent
    tool=hashlib.sha256(''.join(sha256(p) for p in sorted(package.glob('*.py'))).encode()).hexdigest()
    configs=[p for p in book.output.glob('*') if p.name in ['hugo.toml','config.toml','hugo.yaml','config.yaml','config.json']]
    return {'tool':tool,'prompt':prompts.VERSION,'extractor':EXTRACTOR_VERSION,'site_config':hashlib.sha256(''.join(sha256(p) for p in sorted(configs)).encode()).hexdigest()}

def audit_assets(evidence,existing,client):
    figures=[i for i in evidence.items if i.kind=='figure']
    if not figures: return []
    result,_=client.respond(prompts.REVIEW+' Map each source figure to the existing image filename in this Markdown; do not invent missing images.',{'source_figures':[i.model_dump() for i in figures],'markdown':existing.body,'available_files':list(existing.assets)},[],FigureMatches)
    records=[]; seen=set()
    for match in result.matches:
        item=next((i for i in figures if i.id==match.item_id),None)
        if not item or match.item_id in seen or match.path not in existing.assets: raise ValueError('Invalid existing figure mapping')
        seen.add(match.item_id); p=checked_path(existing.path.parent,match.path)
        with Image.open(p) as image: width,height=image.size
        if not item.box: raise ValueError('Source figure lacks coordinates')
        records.append(AssetRecord(item_id=item.id,page=item.page,box=item.box,caption=item.caption,path=match.path,sha256=sha256(p),width=width,height=height,local_file=p))
    return records

def run_book(book,limits,mode,run_id=None,force=False,*,client_factory=ModelClient,selected_ids=None):
    root=checked_path(book.output,'.textbook-agent'); root.mkdir(parents=True,exist_ok=True)
    previous=load_state(root,run_id) if run_id else None
    if previous and previous.book.pdf_sha256!=book.pdf_sha256: raise ValueError('Source changed; start a new run with a corrected manifest')
    state=previous or RunState(id=time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8],book=book,limits=limits,mode=mode,started=time.time())
    if previous and selected_ids is None: selected_ids=set(previous.selected_ids)
    state.selected_ids=sorted(selected_ids or [])
    state.book=book; state.limits=limits; state.mode=mode; state.status='running'
    work=checked_path(root,f'runs/{state.id}'); prior_elapsed=state.elapsed; clock=time.monotonic()
    sampler=ResourceSampler(root)
    def checkpoint():
        state.elapsed=prior_elapsed+time.monotonic()-clock; save_state(root,state)
    def record_usage(usage):
        if not any(u.response_id==usage.response_id for u in state.usage): state.usage.append(usage)
        checkpoint()
    effective_limits=limits.model_copy()
    if previous and limits.max_seconds:
        remaining=limits.max_seconds-state.elapsed
        if remaining<=0: raise AgentError('Run duration budget already reached; increase it explicitly to resume','budget')
        effective_limits.max_seconds=remaining
    client=CachedClient(book,effective_limits,root/'cache',state,client_factory,record_usage,force)
    with book_lock(root):
        for journal in (root/'transactions').glob('*/journal.json'):
            if Path(json.loads(journal.read_text())['root']).resolve()!=book.output.resolve(): raise ValueError('Unsafe recovery root')
            recover_transaction(journal)
        checkpoint(); sampler.start()
        try:
            book=discover_lessons(book,client,root/'cache'); state.book=book
            if selected_ids and not selected_ids<=({x.id for x in book.lessons}|{x.slug for x in book.lessons}): raise ValueError('Unknown selected lesson after chapter discovery')
            atomic_json(checked_path(root,f'books/{book.book_id}.json'),book.model_dump(mode='json'))
            for lesson in book.lessons:
                if selected_ids and lesson.id not in selected_ids and lesson.slug not in selected_ids: continue
                print(f'[{lesson.weight}] {lesson.title}: checking',flush=True)
                target=lesson_path(book,lesson); record=state.lessons.setdefault(lesson.id,{})
                stage=checked_path(work,f'staging/{lesson.slug}'); stage.mkdir(parents=True,exist_ok=True)
                client.lesson_calls=record.get('model_attempts',0) if previous else 0
                @contextmanager
                def timed(name):
                    record['stage']=name; checkpoint(); start=time.monotonic()
                    try: yield
                    finally:
                        state.events.append({'lesson':lesson.id,'stage':name,'seconds':time.monotonic()-start})
                        record['model_attempts']=client.lesson_calls; checkpoint()
                try:
                    existing=read_existing(target)
                    if mode!='audit' and existing and existing.aids_modified: raise ValueError('Study aids were edited or have no provenance; preserve them in a teacher supplement before regeneration')
                    current=fingerprint(book,lesson,existing,versions(book))
                    receipt_path=checked_path(root,f'validated/{book.book_id}/{lesson.slug}.json')
                    if receipt_path.exists() and not force:
                        receipt=json.loads(receipt_path.read_text())
                        if receipt['fingerprint']==current:
                            record.update(status='unchanged',source_fidelity='previously model-reviewed',issues=[],changed_files=[]); checkpoint(); continue
                    if previous and record.get('input_fingerprint')!=current:
                        for p in stage.glob('*.json'): p.unlink()
                    record['input_fingerprint']=current
                    with timed('source-inventory'):
                        evidence=inventory_lesson(book,lesson,client,root/'cache')
                        atomic_json(stage/'evidence.json',evidence.model_dump(mode='json'))
                    record['source_pages']=[p.page for p in evidence.pages]
                    record['source_item_ids']=[i.id for i in evidence.items]
                    if existing:
                        for ref in existing.assets:
                            src=checked_path(target.parent,ref)
                            if src.is_file():
                                dest=checked_path(stage,ref); dest.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dest)
                    if mode=='audit':
                        if not existing:
                            record.update(status='needs-review',issues=['Lesson file is missing'],source_fidelity='unverified'); checkpoint(); continue
                        markdown=existing.front_matter+existing.body+existing.managed_aids
                        with timed('existing-figure-mapping'): assets=audit_assets(evidence,existing,client)
                        draft=None
                    else:
                        with timed('draft'):
                            cached=stage/'draft.json'
                            draft=LessonDraft.model_validate_json(cached.read_text()) if previous and cached.exists() and record.get('input_fingerprint')==current and not force else draft_lesson(evidence,existing,client)
                            atomic_json(cached,draft.model_dump(mode='json'))
                        with timed('assets'):
                            assets=crop_assets(evidence,draft.assets,stage)
                            markdown=assemble_lesson(lesson,existing,draft,assets)
                    with timed('source-review'):
                        review=review_lesson(evidence,markdown,assets,client)
                        for _ in range(limits.repairs if draft else 0):
                            if not any(f.blocking for f in review.findings): break
                            draft=repair_sections(evidence,draft,review,client)
                            assets=crop_assets(evidence,draft.assets,stage)
                            markdown=assemble_lesson(lesson,existing,draft,assets)
                            review=review_lesson(evidence,markdown,assets,client)
                        atomic_json(stage/'review.json',review.model_dump(mode='json'))
                    record['coverage']={'verified':review.covered_ids,'source_count':len(evidence.items)}
                    record['teacher_approved']=False
                    if draft:
                        if not set(review.verified_aid_ids)<={a.id for a in draft.aids}: raise ValueError('Reviewer verified an unknown study aid')
                        pending=[a for a in draft.aids if a.id not in review.verified_aid_ids]
                        if any(not f.blocking for f in review.findings): pending=list(draft.aids)
                        atomic_json(stage/'pending-study-aids.json',{'aids':[a.model_dump() for a in pending]})
                        draft.aids=[a for a in draft.aids if a not in pending]
                        record['pending_study_aids']=[a.id for a in pending]; record['change_notes']=draft.notes
                        markdown=assemble_lesson(lesson,existing,draft,assets)
                    (stage/'_index.md').write_text(markdown,encoding='utf-8')
                    with timed('validation'):
                        validation=validate_lesson(markdown,lesson,evidence,assets,stage)
                        if validation.passing:
                            site=validate_site(book,{lesson.slug:stage},work/'site-validation')
                            validation.errors.extend(site.errors); validation.warnings.extend(site.warnings); validation.site_status=site.site_status
                    issues=[f.message for f in review.findings if f.blocking]+validation.errors
                    record['issues']=issues; record['warnings']=validation.warnings+[f.message for f in review.findings if not f.blocking]
                    record['validation']=validation.model_dump(); record['source_fidelity']='model-reviewed' if not issues else 'unverified'
                    record['assets']=[a.model_dump(mode='json') for a in assets]
                    if issues: record['status']='needs-review'; checkpoint(); continue
                    if mode=='audit': record['status']='audited'; record['changed_files']=[]
                    else:
                        with timed('apply'): changed=apply_lesson(book,lesson,stage,existing)
                        record['status']='applied'; record['changed_files']=[str(p) for p in changed]
                        atomic_json(receipt_path,{'fingerprint':fingerprint(book,lesson,read_existing(target),versions(book)),'run_id':state.id,'review':'model-reviewed','teacher_approved':False})
                    checkpoint()
                except AgentError as exc:
                    record.update(status='interrupted',issues=[str(exc)],source_fidelity='unverified'); state.status='interrupted'; checkpoint(); break
                except (ValueError,OSError) as exc:
                    record.update(status='needs-review',issues=[str(exc)],source_fidelity='unverified'); checkpoint()
            if state.status!='interrupted': state.status='needs-review' if any(r.get('status')=='needs-review' for r in state.lessons.values()) else 'complete'
        except (ValueError,OSError) as exc:
            state.status='needs-review'; state.events.append({'error':str(exc),'category':'source-or-configuration'})
        except AgentError as exc:
            state.status='interrupted'; state.events.append({'error':str(exc),'category':exc.category})
        finally:
            state.resources=sampler.stop()
            if client.backend: state.resources['unknown_request_outcomes']=getattr(client.backend,'unknown_requests',0)
            checkpoint(); paths=write_report(book,state,work/'reports')
            print(f'Run {state.id}: {state.status}\nReport: {paths[0]}',flush=True)
    return state
