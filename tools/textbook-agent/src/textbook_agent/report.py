import json,re,os
from pathlib import Path
from .state import atomic_json

def usage_totals(rows):
    unique={u.response_id:u for u in rows}; data=list(unique.values())
    totals={}
    for key in ['input_tokens','cached_input_tokens','output_tokens','reasoning_tokens']:
        values=[getattr(u,key) for u in data]
        totals[key]=sum(values) if all(v is not None for v in values) else None
    totals['total_tokens']=totals['input_tokens']+totals['output_tokens'] if totals['input_tokens'] is not None and totals['output_tokens'] is not None else None
    totals['uncached_input_tokens']=totals['input_tokens']-totals['cached_input_tokens'] if totals['input_tokens'] is not None and totals['cached_input_tokens'] is not None else None
    totals['recorded_responses']=len(data)
    return totals

def estimate_cost(totals,prices):
    if not prices or not prices.get('effective_date') or any(totals[k] is None for k in ['uncached_input_tokens','cached_input_tokens','output_tokens']): return None
    return {'amount':sum(totals[k]*prices[p]/1_000_000 for k,p in [('uncached_input_tokens','input_per_million'),('cached_input_tokens','cached_per_million'),('output_tokens','output_per_million')]),'currency':prices.get('currency','USD'),'price_effective_date':prices['effective_date'],'label':'Estimate from recorded responses, not the final API bill'}

def redact(text):
    key=os.getenv('OPENAI_API_KEY')
    if key: text=text.replace(key,'[redacted-key]')
    return re.sub(r'sk-[A-Za-z0-9_-]{16,}','[redacted-key]',text)

def write_report(book,state,report_dir):
    report_dir.mkdir(parents=True,exist_ok=True)
    totals=usage_totals(state.usage)
    data={'book_id':book.book_id,'medium':book.medium,'run_id':state.id,'status':state.status,'elapsed_seconds':state.elapsed,'tokens':totals,'resources':state.resources,'excluded_source_sections':book.excluded_sections,'lessons':state.lessons,'events':state.events,'usage':[u.model_dump() for u in state.usage],'teacher_approval':'not recorded','live_model_calls':len(state.usage)}
    rows=['# Textbook agent run report','',f'Book: {book.book_id} | Medium: {book.medium} | Run: {state.id}',f'Status: {state.status}',f'Elapsed: {state.elapsed:.2f} seconds','Teacher approval: not recorded','', '## Recorded API usage','']
    rows.extend(f'- {k}: {v if v is not None else "unknown"}' for k,v in totals.items())
    rows+=['','Cached input is included in input tokens; reasoning is included in output tokens. These are recorded API responses, not a bill. Unknown request outcomes may incur charges not represented here.','','## Lesson results','', '| Lesson | Status | Source review | Issues |','|---|---|---|---|']
    for lesson in book.lessons:
        r=state.lessons.get(lesson.id,{})
        issues='; '.join(r.get('issues',[])).replace('|','/').replace('\n',' ')
        rows.append(f'| {lesson.title.replace("|","/")} | {r.get("status","not processed")} | {r.get("source_fidelity","unverified")} | {issues} |')
    rows+=['','## Local system measurements','',json.dumps(state.resources,ensure_ascii=False,indent=2),'','## Source exclusions','']
    rows.extend('- '+x for x in book.excluded_sections or ['No excluded sections recorded; this does not certify coverage outside selected lesson ranges.'])
    rows+=['','Full coverage mappings, change notes, source pages, per-stage timing, and verification findings are in the accompanying JSON and per-lesson staging files. Automated/model review is not a guarantee of perfect content.']
    md=report_dir/'report.md'; output=report_dir/'report.json'
    md.write_text(redact('\n'.join(rows)+'\n'),encoding='utf-8')
    atomic_json(output,json.loads(redact(json.dumps(data,ensure_ascii=False))))
    return md,output
