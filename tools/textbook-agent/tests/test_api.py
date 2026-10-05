from types import SimpleNamespace as NS
import pytest
from pydantic import BaseModel
from textbook_agent.api import ModelClient, AgentError
from textbook_agent.models import RunLimits

class Answer(BaseModel):
    value: str

class Transport:
    def __init__(self,sequence): self.sequence=iter(sequence); self.requests=[]
    def __call__(self,**kwargs):
        self.requests.append(kwargs); item=next(self.sequence)
        if isinstance(item,Exception): raise item
        return item

def response(status='completed',parsed=None):
    return NS(id='resp_1',_request_id='req_1',status=status,output=[],output_parsed=parsed or Answer(value='yes'),usage=NS(input_tokens=100,output_tokens=10,input_tokens_details=NS(cached_tokens=50),output_tokens_details=NS(reasoning_tokens=3)))

def test_usage_and_budget():
    t=Transport([response()]); client=ModelClient('test',RunLimits(token_limit=100),transport=t)
    result,usage=client.respond('review',{},[],Answer)
    assert result.value=='yes' and usage.input_tokens==100 and usage.cached_input_tokens==50
    assert t.requests[0]['store'] is False
    with pytest.raises(AgentError,match='budget'): client.respond('review',{},[],Answer)

def test_incomplete_does_not_become_content():
    c=ModelClient('test',RunLimits(),transport=Transport([response('incomplete')]))
    with pytest.raises(AgentError,match='incomplete'): c.respond('review',{},[],Answer)
    assert len(c.usage)==1

def test_transient_retry_is_bounded():
    from openai import APIConnectionError
    import httpx
    err=APIConnectionError(request=httpx.Request('POST','https://api.openai.com'))
    t=Transport([err,err,err]); c=ModelClient('test',RunLimits(),transport=t,sleeper=lambda _:None)
    with pytest.raises(AgentError): c.respond('review',{},[],Answer)
    assert len(t.requests)==3 and c.unknown_requests==3

def test_quota_is_not_retried():
    from openai import RateLimitError
    import httpx
    req=httpx.Request('POST','https://api.openai.com'); resp=httpx.Response(429,request=req)
    err=RateLimitError('quota',response=resp,body={'code':'insufficient_quota'})
    t=Transport([err]); c=ModelClient('test',RunLimits(),transport=t,sleeper=lambda _:None)
    with pytest.raises(AgentError,match='quota'): c.respond('review',{},[],Answer)
    assert len(t.requests)==1
