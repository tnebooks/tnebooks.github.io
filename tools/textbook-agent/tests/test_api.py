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
    return NS(id='resp_1',_request_id='req_1',status=status,output=[],output_text=(parsed or Answer(value='yes')).model_dump_json(),usage=NS(input_tokens=100,output_tokens=10,input_tokens_details=NS(cached_tokens=50),output_tokens_details=NS(reasoning_tokens=3)))

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

def test_jpeg_uses_correct_image_mime(tmp_path):
    from PIL import Image
    p=tmp_path/'figure.jpg'; Image.new('RGB',(20,20),'white').save(p)
    t=Transport([response()]); c=ModelClient('test',RunLimits(),transport=t)
    c.respond('review',{},[p],Answer)
    assert t.requests[0]['input'][0]['content'][1]['image_url'].startswith('data:image/jpeg;')

@pytest.mark.parametrize('status,text,category',[('incomplete','{"value":','incomplete'),('completed','{"value":','invalid-output'),('completed','{"value":"yes"}',None)])
def test_real_sdk_records_usage_before_json_parsing(monkeypatch,status,text,category):
    import httpx
    from openai import OpenAI
    import textbook_agent.api as api
    body={'id':'resp_sdk','object':'response','created_at':1,'model':'test','status':status,'output':[{'id':'msg_1','type':'message','role':'assistant','status':status,'content':[{'type':'output_text','text':text,'annotations':[]}]}],'parallel_tool_calls':False,'tool_choice':'auto','tools':[],'usage':{'input_tokens':100,'output_tokens':10,'total_tokens':110,'input_tokens_details':{'cached_tokens':50},'output_tokens_details':{'reasoning_tokens':3}}}
    requests=[]
    def handler(request):
        import json
        requests.append(json.loads(request.content))
        return httpx.Response(200,json=body,headers={'x-request-id':'req_sdk'})
    sdk=OpenAI(api_key='offline-test',http_client=httpx.Client(transport=httpx.MockTransport(handler)),max_retries=0)
    monkeypatch.setenv('OPENAI_API_KEY','offline-test')
    monkeypatch.setattr(api,'OpenAI',lambda **kwargs:sdk)
    recorded=[]; client=api.ModelClient('test',RunLimits(),on_usage=recorded.append)
    if category:
        with pytest.raises(api.AgentError) as failure: client.respond('review',{},[],Answer)
        assert failure.value.category==category
    else:
        result,_=client.respond('review',{},[],Answer)
        assert result.value=='yes'
    assert len(recorded)==1 and recorded[0].output_tokens==10
    assert client.usage[0].request_id=='req_sdk'
    assert requests[0]['text']['format']['type']=='json_schema'
    assert requests[0]['text']['format']['strict'] is True
    sdk.close()
