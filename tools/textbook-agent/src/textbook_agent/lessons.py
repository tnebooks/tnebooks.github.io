import hashlib,re,json
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlparse,unquote
import yaml
from markdown_it import MarkdownIt
from .models import ExistingLesson,LessonDraft,AssetSpec
from .config import sha256
from .paths import checked_path
from . import prompts

AID_START='<!-- textbook-agent:study-aids -->'
AID_END='<!-- /textbook-agent:study-aids -->'

def section_hash(text: str) -> str: return hashlib.sha256(text.encode()).hexdigest()

def split_sections(body: str) -> dict[str,str]:
    lines=body.splitlines(keepends=True); cuts=[0]
    for token in MarkdownIt().parse(body):
        if token.type=='heading_open' and token.tag in ['h1','h2'] and token.map and token.map[0]>0: cuts.append(token.map[0])
    cuts=sorted(set(cuts))+[len(lines)]
    return {f'section-{i}':''.join(lines[a:b]) for i,(a,b) in enumerate(zip(cuts,cuts[1:])) if b>a}

def image_refs(markdown: str) -> list[str]:
    refs=[]
    for token in MarkdownIt().parse(markdown):
        for child in token.children or []:
            if child.type=='image': refs.append(child.attrGet('src'))
    return refs

def read_existing(path: Path) -> ExistingLesson | None:
    if not path.exists(): return None
    if path.is_symlink(): raise ValueError('Symlink lesson is not supported')
    raw=path.read_text(encoding='utf-8'); front=''; body=raw
    match=re.match(r'\A---\r?\n.*?\r?\n---(?:\r?\n|$)',raw,re.S)
    if match: front=match.group(); body=raw[len(front):]
    if AID_START in body:
        if body.count(AID_START)!=1 or body.count(AID_END)!=1: raise ValueError('Malformed managed study-aid block')
        body=re.sub(re.escape(AID_START)+'.*?'+re.escape(AID_END), '',body,flags=re.S)
    assets={}
    for ref in image_refs(raw):
        if urlparse(ref).scheme: continue
        p=checked_path(path.parent,unquote(urlparse(ref).path))
        assets[ref]=sha256(p) if p.is_file() else 'missing'
    return ExistingLesson(path=path,front_matter=front,body=body,sha256=sha256(path),assets=assets,sections=split_sections(body))

def source_groups(evidence,existing):
    groups=[]; current=[]
    for item in evidence.items:
        if item.kind=='heading' and current:
            groups.append(current); current=[]
        current.append(item)
    if current: groups.append(current)
    if not existing: return [(f'new-{i}',group) for i,group in enumerate(groups)]
    matched={}; order=[]
    for group in groups:
        title=group[0].text.strip().casefold()
        def normalize(value): return re.sub(r'^\s*(?:\d+(?:\.\d+)*[.)]?\s*)', '',value.lstrip('# ').casefold()).strip()
        scores=[]
        for anchor,section in existing.sections.items():
            headings=re.findall(r'(?m)^#{1,6}\s+(.+)$',section) or [section.lstrip().split('\n',1)[0]]
            scores.append((max(SequenceMatcher(None,normalize(title),normalize(h)).ratio() for h in headings),anchor))
        if group[0].kind!='heading' and not groups.index(group):
            first=next(iter(existing.sections),None)
            if first: scores.append((1,first))
        score,anchor=max(scores,default=(0,None))
        if score<.45: anchor=f'new-{len(order)}'
        if anchor not in matched: matched[anchor]=[]; order.append(anchor)
        matched[anchor].extend(group)
    return [(anchor,matched[anchor]) for anchor in order]

def draft_lesson(evidence,existing,client):
    edits=[]; specs=[]; notes=[]; prior=None
    for anchor,items in source_groups(evidence,existing):
        sections=existing.sections if existing else {}
        if anchor in sections: candidates={anchor:sections[anchor]}
        else: candidates={}
        part,_=client.respond(prompts.DRAFT,{'medium':evidence.medium,'target_anchor':anchor,'after_anchor':prior,'source_items':[i.model_dump() for i in items],'existing_sections':[{'anchor':a,'sha256':section_hash(s),'markdown':s} for a,s in candidates.items()]},[],LessonDraft)
        if part.aids: raise ValueError('Source draft unexpectedly contains study aids')
        for edit in part.edits:
            if edit.anchor!=anchor: raise ValueError('Draft edited an unrelated section')
            if edit.expected_sha256!=(section_hash(sections[anchor]) if anchor in sections else None): raise ValueError('Draft section hash mismatch')
            edit.after_anchor=prior if anchor not in sections else None
        if not part.edits: raise ValueError('Draft omitted its source section mapping')
        edits.extend(part.edits); specs.extend(part.assets); notes.extend(part.notes); prior=anchor
    represented=[x for edit in edits for x in edit.item_ids]
    if len(set(represented))!=len(represented) or set(represented)!={i.id for i in evidence.items}: raise ValueError('Draft source mappings are incomplete or duplicated')
    required={i.id for i in evidence.items if i.kind=='figure'}
    if not required.issubset({s.item_id for s in specs}): raise ValueError('Draft omitted textbook figure crops')
    result=LessonDraft(edits=edits,assets=specs,aids=[],notes=notes)
    # Aids are separate and can fail without losing complete source content.
    aids,_=client.respond(prompts.AIDS,{'medium':evidence.medium,'source_items':[i.model_dump() for i in evidence.items]},[],LessonDraft)
    if aids.edits or aids.assets: raise ValueError('Study-aid response attempted source edits')
    source_ids={i.id for i in evidence.items}
    if len({a.id for a in aids.aids})!=len(aids.aids): raise ValueError('Duplicate study-aid IDs')
    for aid in aids.aids:
        if not re.fullmatch(r'[a-zA-Z0-9.-]+',aid.id): raise ValueError('Unsafe study-aid ID')
        if not aid.source_item_ids or not set(aid.source_item_ids)<=source_ids: raise ValueError('Unsupported study aid')
    result.aids=aids.aids; result.notes.extend(aids.notes)
    return result

def assemble_lesson(lesson,existing,draft,assets):
    sections=dict(existing.sections) if existing else {}; order=list(sections)
    asset_map={a.item_id:a for a in assets}; changed=set()
    for edit in draft.edits:
        if edit.anchor in changed: raise ValueError('Duplicate section edits')
        changed.add(edit.anchor)
        if edit.anchor in sections:
            if edit.expected_sha256!=section_hash(sections[edit.anchor]): raise ValueError('Stale section edit')
        else:
            if edit.expected_sha256 is not None: raise ValueError('Unknown edited section')
            if edit.after_anchor:
                if edit.after_anchor not in order: raise ValueError('Missing insertion anchor')
                order.insert(order.index(edit.after_anchor)+1,edit.anchor)
            elif existing and len(changed)==1: order.insert(0,edit.anchor)
            else: order.append(edit.anchor)
        def replace(match):
            item=match.group(1)
            if item not in asset_map: raise ValueError('Unbound source asset')
            a=asset_map[item]; caption=a.caption.replace('[','(').replace(']',')').replace('\n',' ')
            return f'![{caption} (PDF page {a.page})]({a.path})'
        content=re.sub(r'\{\{asset:([^}]+)\}\}',replace,edit.markdown)
        marker='<!-- textbook-items: '+json.dumps(edit.item_ids)+' -->\n'
        first,sep,rest=content.partition('\n')
        sections[edit.anchor]=first+sep+marker+rest+'\n\n'
    front=existing.front_matter if existing and existing.front_matter else '---\n'+yaml.safe_dump({'title':lesson.title,'weight':lesson.weight},allow_unicode=True,sort_keys=False)+'---\n'
    body=''.join(sections[a] for a in order)
    if draft.aids:
        body+='\n\n'+AID_START+'\n\n'+('\n\n'.join('<!-- textbook-aid:'+a.id+' -->\n'+a.markdown for a in draft.aids))+'\n\n'+AID_END+'\n'
    return front+body
