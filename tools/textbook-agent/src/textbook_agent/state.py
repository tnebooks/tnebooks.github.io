import json,hashlib,os,tempfile,fcntl
from pathlib import Path
from contextlib import contextmanager
from .models import RunState
from .paths import checked_path

def atomic_json(path: Path,data: dict) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.state-',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            json.dump(data,f,ensure_ascii=False,indent=2); f.flush(); os.fsync(f.fileno())
        os.replace(name,path)
        descriptor=os.open(path.parent,os.O_RDONLY)
        try: os.fsync(descriptor)
        finally: os.close(descriptor)
    finally:
        if os.path.exists(name): os.unlink(name)

def fingerprint(book,lesson,existing,versions):
    payload={'pdf':book.pdf_sha256,'lesson':lesson.model_dump(mode='json'),'medium':book.medium,'class':book.class_name,'subject':book.subject,'edition':book.edition,'term':book.term,'volume':book.volume,'model':book.model,'glossary':book.glossary,'versions':versions,'markdown':existing.sha256 if existing else None,'assets':existing.assets if existing else {}}
    return hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()

def save_state(root: Path,state: RunState) -> None:
    path=checked_path(root,f'runs/{state.id}/state.json'); atomic_json(path,state.model_dump(mode='json'))

def load_state(root: Path,run_id: str) -> RunState:
    return RunState.model_validate_json(checked_path(root,f'runs/{run_id}/state.json').read_text(encoding='utf-8'))

@contextmanager
def book_lock(root: Path):
    root.mkdir(parents=True,exist_ok=True)
    p=checked_path(root,'agent.lock')
    with p.open('a+') as f:
        try: fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: raise ValueError('Another textbook run is writing to this destination') from None
        try: yield
        finally: fcntl.flock(f,fcntl.LOCK_UN)
