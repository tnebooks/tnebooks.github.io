import re,json,subprocess,shutil
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlparse,unquote
import xml.etree.ElementTree as ET
import yaml
from PIL import Image
from markdown_it import MarkdownIt
from .models import ValidationResult
from .lessons import image_refs
from .paths import checked_path
from .config import sha256

class Images(HTMLParser):
    def __init__(self): super().__init__(); self.refs=[]
    def handle_starttag(self,tag,attrs):
        if tag=='img': self.refs.append(dict(attrs).get('src',''))

def check_math(markdown: str) -> list[str]:
    lines=markdown.splitlines(keepends=True)
    for token in MarkdownIt().parse(markdown):
        if token.type in ['fence','code_block'] and token.map:
            for n in range(*token.map): lines[n]='\n'
    text=''.join(lines); errors=[]
    expressions=[]
    for left,right,pattern in [(r'\(',r'\)',r'\\\((.*?)\\\)'),(r'\[',r'\]',r'\\\[(.*?)\\\]'),('$$','$$',r'\$\$(.*?)\$\$')]:
        if (left!=right and text.count(left)!=text.count(right)) or (left==right and text.count(left)%2): errors.append('Unbalanced math delimiters')
        expressions.extend(re.findall(pattern,text,re.S))
    if not expressions: return errors
    node=shutil.which('node')
    if not node: return errors+['Math validation requires Node.js and package-local KaTeX']
    try:
        p=subprocess.run([node,str(Path(__file__).with_name('math_check.mjs'))],input=json.dumps(expressions),text=True,capture_output=True,timeout=30)
        if p.returncode: return errors+['Math validator unavailable; run npm install in the agent runtime directory']
        errors.extend('Invalid math: '+x for x in json.loads(p.stdout)['errors'])
    except (OSError,ValueError,subprocess.TimeoutExpired): errors.append('Math validation failed')
    return errors

def validate_lesson(markdown,lesson,evidence,assets,staging):
    errors=[]; warnings=[]
    try:
        if not markdown.startswith('---\n'): raise ValueError('Missing front matter')
        metadata=yaml.safe_load(markdown.split('---',2)[1])
        if not isinstance(metadata,dict) or not metadata.get('title') or metadata.get('weight')!=lesson.weight: raise ValueError('Invalid title/weight')
    except (ValueError,IndexError,yaml.YAMLError): errors.append('Invalid lesson YAML/front matter')
    if re.search(r'<\s*(script|iframe|object|embed)\b|\bon\w+\s*=|javascript\s*:',markdown,re.I): errors.append('Unsafe executable HTML in lesson')
    parser=Images(); parser.feed(markdown)
    refs=image_refs(markdown)+parser.refs
    for ref in refs:
        scheme=urlparse(ref).scheme
        if scheme in ['http','https']: warnings.append('External image is not source verified: '+ref); continue
        try:
            p=checked_path(staging,unquote(urlparse(ref).path))
            if not p.is_file(): raise ValueError('missing')
            if p.suffix.lower()=='.svg':
                svg=p.read_text(encoding='utf-8'); ET.fromstring(svg)
                if re.search(r'<script|\bon\w+=|javascript:',svg,re.I): raise ValueError('unsafe SVG')
            else:
                with Image.open(p) as im: im.verify()
        except (ValueError,OSError,ET.ParseError): errors.append('Invalid or missing image: '+ref)
    for asset in assets:
        try:
            p=checked_path(staging,asset.path)
            if sha256(p)!=asset.sha256 or asset.path not in refs: raise ValueError('asset mismatch')
        except (ValueError,OSError): errors.append('Source asset mismatch or unreferenced: '+asset.path)
    for item in evidence.items:
        if item.kind=='figure' and not any(a.item_id==item.id for a in assets): errors.append('Missing source figure: '+item.id)
    mappings=[]
    for raw in re.findall(r'<!-- textbook-items: (.*?) -->',markdown):
        try: mappings.extend(json.loads(raw))
        except ValueError: errors.append('Invalid source coverage marker')
    if mappings and (len(set(mappings))!=len(mappings) or set(mappings)!={i.id for i in evidence.items}): errors.append('Incomplete or duplicate source coverage mapping')
    if '{{asset:' in markdown: errors.append('Unresolved source asset placeholder')
    errors.extend(check_math(markdown))
    return ValidationResult(errors=errors,warnings=warnings)
