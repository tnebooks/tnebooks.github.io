from pathlib import Path
from .models import BookManifest, LessonSpec

def checked_path(root: Path, relative: str) -> Path:
    rel=Path(relative)
    if rel.is_absolute() or '..' in rel.parts: raise ValueError('Unsafe relative path')
    p=root/rel
    if not p.resolve().is_relative_to(root.resolve()): raise ValueError('Symlink escapes root')
    if any(x.is_symlink() for x in [p,*p.parents] if x!=root.parent and x.is_relative_to(root)):
        raise ValueError('Symlink destination is not supported')
    return p

def lesson_path(book: BookManifest, lesson: LessonSpec) -> Path:
    return checked_path(book.output,f'content.{book.medium}/docs/{lesson.slug}/_index.md')
