import ast,operator,math,re
from .models import ReviewResult,Finding,LessonDraft
from .lessons import split_sections,section_hash,AID_START,AID_END
from . import prompts

OPS={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,ast.Pow:operator.pow}

def numeric_value(expression: str) -> float:
    if len(expression)>200: raise ValueError('Expression too long')
    def walk(node):
        if isinstance(node,ast.Constant) and type(node.value) in [int,float] and abs(node.value)<1e100: return node.value
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.USub,ast.UAdd)): return (-1 if isinstance(node.op,ast.USub) else 1)*walk(node.operand)
        if isinstance(node,ast.BinOp) and type(node.op) in OPS:
            a,b=walk(node.left),walk(node.right)
            if isinstance(node.op,ast.Pow) and abs(b)>100: raise ValueError('Exponent too large')
            value=OPS[type(node.op)](a,b)
            if not isinstance(value,(int,float)) or not math.isfinite(value) or abs(value)>1e100: raise ValueError('Unbounded numeric value')
            return value
        raise ValueError('Only numeric arithmetic is allowed')
    try: return walk(ast.parse(expression,mode='eval').body)
    except (SyntaxError,ZeroDivisionError,OverflowError,RecursionError) as exc: raise ValueError('Invalid numeric expression') from exc

def review_lesson(evidence,markdown,assets,client):
    findings=[]; covered=set(); verified=set(); window=getattr(getattr(client,'limits',None),'page_window',2)
    for offset in range(0,len(evidence.pages),window):
        pages=evidence.pages[offset:offset+window]; numbers={p.page for p in pages}
        items=[i for i in evidence.items if i.page in numbers]
        ids={i.id for i in items}
        sections=split_sections(markdown)
        relevant=[s for s in sections.values() if any(f'"{i}"' in s for i in ids)]
        context='\n'.join(relevant) if relevant else markdown
        result,_=client.respond(prompts.REVIEW,{'medium':evidence.medium,'source_items':[i.model_dump() for i in items],'markdown':context,'assets':[a.model_dump() for a in assets if a.page in numbers]},[p.image for p in pages],ReviewResult)
        if not set(result.covered_ids)<=ids: raise ValueError('Reviewer returned unrelated source IDs')
        covered.update(result.covered_ids); findings.extend(result.findings)
    for asset in assets:
        page=next(p for p in evidence.pages if p.page==asset.page)
        result,_=client.respond(prompts.REVIEW+' Check specifically whether this crop preserves all source figure labels and content.',{'asset':asset.model_dump(),'markdown':markdown if len(markdown)<20000 else asset.caption},[page.image,asset.local_file] if asset.local_file else [page.image],ReviewResult)
        findings.extend(result.findings)
    if AID_START in markdown:
        aid_text=markdown.split(AID_START,1)[1].split(AID_END,1)[0]
        result,_=client.respond(prompts.REVIEW+' Review the study aids only; flag unsupported answers and verify arithmetic steps.',{'medium':evidence.medium,'source_items':[i.model_dump() for i in evidence.items],'study_aids':aid_text},[],ReviewResult)
        verified.update(result.verified_aid_ids)
        findings.extend(result.findings)
        for expression,answer in re.findall(r'`([0-9.+*/() -]+)`\s*=\s*([0-9.eE+-]+)',aid_text):
            try:
                if not math.isclose(numeric_value(expression),float(answer),rel_tol=1e-7,abs_tol=1e-9): findings.append(Finding(item_id=None,section='study-aids',message='Generated numeric arithmetic is incorrect',blocking=False)); verified.clear()
            except ValueError: verified.clear()
    for item in evidence.items:
        if item.id not in covered: findings.append(Finding(item_id=item.id,section=None,message='Source item not verified in staged content',blocking=True))
    return ReviewResult(covered_ids=sorted(covered),findings=findings,verified_aid_ids=sorted(verified),teacher_approved=False)

def repair_sections(evidence,draft,review,client):
    failed={f.section for f in review.findings if f.blocking and f.section}
    failed.update(e.anchor for e in draft.edits if any(f.blocking and f.item_id in e.item_ids for f in review.findings))
    if not failed: return draft
    selected=[e for e in draft.edits if e.anchor in failed]
    if not selected: raise ValueError('Review issue cannot be mapped to a repairable source section')
    repaired,_=client.respond(prompts.REPAIR,{'medium':evidence.medium,'source_items':[i.model_dump() for i in evidence.items if any(i.id in e.item_ids for e in selected)],'existing_sections':[{'anchor':e.anchor,'sha256':section_hash(e.markdown),'markdown':e.markdown} for e in selected],'findings':[f.model_dump() for f in review.findings if f.blocking]},[],LessonDraft)
    if repaired.aids: raise ValueError('Repair attempted unrelated aid edits')
    old={e.anchor:e for e in selected}; replacements={}
    for e in repaired.edits:
        if e.anchor not in old or e.expected_sha256!=section_hash(old[e.anchor].markdown): raise ValueError('Repair edited unrelated or stale section')
        e.expected_sha256=old[e.anchor].expected_sha256; e.after_anchor=old[e.anchor].after_anchor
        if set(e.item_ids)!=set(old[e.anchor].item_ids): raise ValueError('Repair lost source coverage')
        replacements[e.anchor]=e
    return draft.model_copy(update={'edits':[replacements.get(e.anchor,e) for e in draft.edits],'assets':[a for a in draft.assets if a.item_id not in {x.item_id for x in repaired.assets}]+repaired.assets,'notes':draft.notes+repaired.notes})
