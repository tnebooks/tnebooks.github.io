import threading,time,os
from pathlib import Path
import psutil

class ResourceSampler:
    def __init__(self,root: Path,interval=1.0,reader=None):
        self.root=root; self.interval=interval; self.reader=reader or self.read_process
        self.stop_event=threading.Event(); self.samples=[]; self.warnings=[]; self.thread=None; self.processes={}
    def read_process(self):
        process=psutil.Process(os.getpid()); processes=[process]+process.children(recursive=True)
        rss=0; cpu=0
        self.processes={p.pid:self.processes.get(p.pid,p) for p in processes}
        for p in self.processes.values():
            try: rss+=p.memory_info().rss; cpu+=p.cpu_percent(interval=None)
            except (psutil.NoSuchProcess,psutil.AccessDenied): continue
        return {'rss_bytes':rss,'cpu_core_percent':cpu}
    def sample(self):
        try: self.samples.append(self.reader())
        except Exception: self.warnings.append('A local resource sample was unavailable')
    def start(self):
        self.sample()
        def loop():
            while not self.stop_event.wait(self.interval): self.sample()
        self.thread=threading.Thread(target=loop,daemon=True); self.thread.start()
    def stop(self):
        self.stop_event.set()
        if self.thread: self.thread.join(timeout=2)
        self.sample()
        disk=sum(p.stat().st_size for p in self.root.rglob('*') if p.is_file() and not p.is_symlink()) if self.root.exists() else 0
        return {'sampling_interval_seconds':self.interval,'sample_count':len(self.samples),'peak_rss_bytes':max((s['rss_bytes'] for s in self.samples),default=None),'peak_cpu_core_percent':max((s['cpu_core_percent'] for s in self.samples),default=None),'cache_disk_bytes':disk,'scope':'agent process and its live child processes; CPU percent is relative to one core; RSS sums can include shared pages; model-server usage unavailable','warnings':list(dict.fromkeys(self.warnings))}
