import os, hashlib, json
from pathlib import Path
import fitz
from .models import BookManifest

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()

def load_manifest(path: Path) -> BookManifest:
    data=json.loads(path.read_text(encoding='utf-8'))
    for key in ['pdf','output']:
        p=Path(data[key]).expanduser(); data[key]=str(p if p.is_absolute() else path.parent/p)
    return resolve_book(data)

def resolve_book(options: dict[str,object]) -> BookManifest:
    data=dict(options); data['model']=data.get('model') or os.getenv('OPENAI_MODEL')
    book=BookManifest.model_validate(data)
    book.pdf=book.pdf.expanduser().resolve(); book.output=book.output.expanduser().resolve()
    if not book.pdf.is_file(): raise ValueError('Source PDF does not exist')
    if not book.model: raise ValueError('Set OPENAI_MODEL or provide --model')
    actual=sha256(book.pdf)
    if book.pdf_sha256 and actual!=book.pdf_sha256: raise ValueError('PDF checksum changed: update the manifest explicitly')
    with fitz.open(book.pdf) as d: count=len(d)
    if book.page_count and count!=book.page_count: raise ValueError('PDF page count mismatch')
    return BookManifest.model_validate({**book.model_dump(),'pdf_sha256':actual,'page_count':count})
