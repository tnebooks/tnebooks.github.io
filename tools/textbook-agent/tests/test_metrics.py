from textbook_agent.metrics import ResourceSampler

def test_local_memory_and_disk_are_separate(tmp_path):
    (tmp_path/'file').write_bytes(b'123')
    sampler=ResourceSampler(tmp_path,reader=lambda:{'rss_bytes':100,'cpu_core_percent':10})
    sampler.start(); result=sampler.stop()
    assert result['peak_rss_bytes']==100 and result['cache_disk_bytes']==3
    assert 'model-server' in result['scope']

def test_cpu_sampler_keeps_previous_cpu_observation(tmp_path,monkeypatch):
    import textbook_agent.metrics as metrics
    class Process:
        pid=7
        def __init__(self,*args): self.calls=0
        def children(self,recursive=True): return []
        def memory_info(self):
            from types import SimpleNamespace
            return SimpleNamespace(rss=100)
        def cpu_percent(self,interval=None): self.calls+=1; return 0 if self.calls==1 else 17
    monkeypatch.setattr(metrics.psutil,'Process',Process)
    sampler=ResourceSampler(tmp_path)
    sampler.read_process()
    assert sampler.read_process()['cpu_core_percent']==17
