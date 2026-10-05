import json,os,shutil,tempfile,uuid
from pathlib import Path
from .paths import checked_path,lesson_path
from .lessons import read_existing
from .config import sha256
from .state import atomic_json

def replace_file(source: Path,target: Path):
    target.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.textbook-',dir=target.parent)
    try:
        with os.fdopen(fd,'wb') as f:
            with source.open('rb') as src: shutil.copyfileobj(src,f)
            f.flush(); os.fsync(f.fileno())
        os.replace(name,target)
    finally:
        if os.path.exists(name): os.unlink(name)

def recover_transaction(journal: Path) -> None:
    data=json.loads(journal.read_text(encoding='utf-8'))
    if data['status'] in ['committed','recovered']: return
    root=Path(data['root'])
    for entry in reversed(data['files']):
        target=checked_path(root,entry['target']); current=sha256(target) if target.exists() else None
        if current not in [entry['old_sha256'],entry['new_sha256'],None]: raise ValueError('Recovery conflict: destination was edited after interruption')
        if entry['backup']:
            backup=checked_path(journal.parent,entry['backup'])
            if sha256(backup)!=entry['old_sha256']: raise ValueError('Recovery backup checksum mismatch')
            replace_file(backup,target)
        elif target.exists(): target.unlink()
    data['status']='recovered'; atomic_json(journal,data)

def apply_lesson(book,lesson,staged,expected):
    target=lesson_path(book,lesson); current=read_existing(target)
    if (current.sha256 if current else None)!=(expected.sha256 if expected else None) or (current.assets if current else {})!=(expected.assets if expected else {}): raise ValueError('Destination conflict: lesson or image changed during this run')
    files=[staged/'_index.md']+sorted(staged.glob('textbook-*.png'))
    if not files[0].is_file(): raise ValueError('No staged lesson')
    root=checked_path(book.output,f'.textbook-agent/transactions/{uuid.uuid4().hex}'); root.mkdir(parents=True,exist_ok=True)
    entries=[]
    for index,source in enumerate(files):
        destination=checked_path(target.parent,source.name)
        backup=f'{index}.bak' if destination.exists() else None
        old=sha256(destination) if destination.exists() else None
        if backup: shutil.copy2(destination,root/backup)
        entries.append({'target':str(destination.relative_to(book.output)),'backup':backup,'old_sha256':old,'new_sha256':sha256(source)})
    journal=root/'journal.json'; data={'root':str(book.output),'status':'applying','files':entries}; atomic_json(journal,data)
    try:
        for source,entry in zip(files,entries): replace_file(source,checked_path(book.output,entry['target']))
        data['status']='committed'; atomic_json(journal,data)
    except Exception:
        recover_transaction(journal); raise
    return [checked_path(book.output,x['target']) for x in entries]
