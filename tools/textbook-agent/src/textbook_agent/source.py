import hashlib, json, shutil, subprocess
from pathlib import Path
from typing import Iterator
import fitz
from PIL import Image, ImageStat, ImageDraw
from .models import BookManifest, LessonSpec, SourcePage
from .config import sha256

EXTRACTOR_VERSION='1'

def inspect_render(path: Path) -> list[str]:
    try:
        with Image.open(path) as im:
            im.load(); gray=im.convert('L'); gray.thumbnail((256,256))
            return ['blank-render'] if ImageStat.Stat(gray).stddev[0]<1 else []
    except (OSError,ValueError): return ['invalid-render']

def alternate_render(pdf: Path, page: int, dest: Path) -> None:
    binary=shutil.which('pdftoppm')
    if binary:
        result=subprocess.run([binary,'-f',str(page),'-l',str(page),'-singlefile','-scale-to','1800','-png',str(pdf),str(dest.with_suffix(''))],capture_output=True,timeout=60)
        if result.returncode==0 and not inspect_render(dest): return
    import pdfplumber
    with pdfplumber.open(pdf) as d: d.pages[page-1].to_image(resolution=150).original.save(dest)

def prepare_pages(book: BookManifest, lesson: LessonSpec, cache: Path) -> Iterator[SourcePage]:
    digest=book.pdf_sha256 or sha256(book.pdf)
    with fitz.open(book.pdf) as doc:
        for n in range(lesson.pdf_start,lesson.pdf_end+1):
            boundary=next((b.box for b in lesson.boundaries if b.page==n),None)
            key=hashlib.sha256(json.dumps([digest,n,boundary,EXTRACTOR_VERSION]).encode()).hexdigest()[:24]
            root=cache/key; root.mkdir(parents=True,exist_ok=True)
            record=root/'page.json'; image=root/'page.png'
            if record.exists() and image.exists():
                saved=SourcePage.model_validate_json(record.read_text())
                if saved.checksum==sha256(image) and (not inspect_render(image) or 'intentional-blank-source-page' in saved.warnings): yield saved; continue
            page=doc[n-1]; w,h=page.rect.width,page.rect.height
            clip=fitz.Rect(boundary[0]*w,boundary[1]*h,boundary[2]*w,boundary[3]*h) if boundary else None
            text=page.get_text('text',sort=True,clip=clip); warnings=[]
            if len(text.strip())<20 or '\ufffd' in text: warnings.append('text-needs-visual-transcription')
            if book.medium=='ta': warnings.append('verify-tamil-font-mapping-visually')
            page.get_pixmap(matrix=fitz.Matrix(2,2),alpha=False).save(image)
            intentional_blank=not text.strip() and not page.get_images() and not page.get_drawings()
            if inspect_render(image) and not intentional_blank:
                try: alternate_render(book.pdf,n,image)
                except Exception: warnings.append('alternate-render-failed')
            if inspect_render(image):
                if intentional_blank: warnings.append('intentional-blank-source-page')
                else: raise ValueError(f'Unreadable source render on PDF page {n}')
            if boundary:
                with Image.open(image) as original:
                    masked=Image.new('RGB',original.size,'white')
                    box=tuple(round(v*(original.width if i%2==0 else original.height)) for i,v in enumerate(boundary))
                    masked.paste(original.crop(box),box); masked.save(image)
            if not text.strip():
                import pdfplumber
                with pdfplumber.open(book.pdf) as alternative:
                    ap=alternative.pages[n-1]
                    if clip: ap=ap.crop(tuple(clip))
                    text=ap.extract_text() or ''
            result=SourcePage(page=n,width=w,height=h,text=text,image=image,checksum=sha256(image),warnings=warnings)
            record.write_text(result.model_dump_json(indent=2),encoding='utf-8'); yield result
