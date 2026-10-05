import hashlib
from pathlib import Path
from PIL import Image
from .models import AssetSpec, AssetRecord, LessonEvidence, Boundary
from .paths import checked_path
from .config import sha256
from .source import inspect_render

def crop_assets(evidence: LessonEvidence, specs: list[AssetSpec], staging: Path) -> list[AssetRecord]:
    result=[]; seen=set()
    for spec in specs:
        Boundary(page=spec.page,box=spec.box)
        if spec.item_id in seen: raise ValueError('Duplicate figure item')
        seen.add(spec.item_id)
        page=next((p for p in evidence.pages if p.page==spec.page),None)
        if not page: raise ValueError('Figure page outside lesson')
        bound=next((b.box for b in evidence.lesson.boundaries if b.page==spec.page),None)
        if bound and not (bound[0]<=spec.box[0]<spec.box[2]<=bound[2] and bound[1]<=spec.box[1]<spec.box[3]<=bound[3]): raise ValueError('Crop outside chapter boundary')
        key=hashlib.sha256(f'{page.checksum}:{spec.box}'.encode()).hexdigest()[:16]
        name=f'textbook-p{spec.page}-{key}.png'; dest=checked_path(staging,name); dest.parent.mkdir(parents=True,exist_ok=True)
        with Image.open(page.image) as image:
            box=tuple(round(v*(image.width if i%2==0 else image.height)) for i,v in enumerate(spec.box))
            crop=image.crop(box)
            if min(crop.size)<12: raise ValueError('Crop too small to be readable')
            crop.save(dest); width,height=crop.size
        if inspect_render(dest): raise ValueError('Blank or invalid figure crop')
        result.append(AssetRecord(**spec.model_dump(),path=name,sha256=sha256(dest),width=width,height=height))
    return result
