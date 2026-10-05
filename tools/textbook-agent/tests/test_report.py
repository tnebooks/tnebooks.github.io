import json
from textbook_agent.report import write_report,usage_totals
from textbook_agent.models import RunState,RunLimits,ApiUsage

def test_cached_and_reasoning_tokens_are_not_double_counted():
    rows=[ApiUsage(response_id='1',input_tokens=100,cached_input_tokens=80,output_tokens=20,reasoning_tokens=10)]*2
    totals=usage_totals(rows)
    assert totals['total_tokens']==120 and totals['uncached_input_tokens']==20
    assert usage_totals([ApiUsage(response_id='unknown')])['total_tokens'] is None

def test_reports_do_not_claim_teacher_approval(book,tmp_path):
    state=RunState(id='test',book=book,limits=RunLimits(),mode='run',started=0,elapsed=5,status='complete',lessons={'1':{'status':'applied','source_fidelity':'model-reviewed','teacher_approved':False}})
    md,data=write_report(book,state,tmp_path/'report')
    assert 'Teacher approval: not recorded' in md.read_text()
    assert json.loads(data.read_text())['elapsed_seconds']==5

def test_explicit_dated_prices_produce_labeled_estimate(book,tmp_path):
    from textbook_agent.models import BookManifest
    book=BookManifest.model_validate({**book.model_dump(),'prices':{'effective_date':'2026-10-05','currency':'USD','input_per_million':2,'cached_per_million':.2,'output_per_million':10}})
    state=RunState(id='priced',book=book,limits=RunLimits(),mode='run',started=0,usage=[ApiUsage(response_id='1',input_tokens=1000,cached_input_tokens=800,output_tokens=100)])
    _,data=write_report(book,state,tmp_path/'report')
    assert abs(json.loads(data.read_text())['estimated_cost']['amount']-.00156)<1e-9
