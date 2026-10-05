import shutil,subprocess,tomllib
from pathlib import Path
from .models import ValidationResult
from .paths import lesson_path

def validate_site(book,staged_lessons,work):
    configs=[book.output/n for n in ['hugo.toml','config.toml','hugo.yaml','config.yaml','config.json'] if (book.output/n).exists()]
    if not configs and not (book.output/'config').is_dir(): return ValidationResult()
    if not shutil.which('hugo'): return ValidationResult(errors=['Hugo is unavailable; lesson remains staged'],site_status='unavailable')
    if work.exists(): shutil.rmtree(work)
    site=work/'site'; public=work/'public'
    shutil.copytree(book.output,site,ignore=shutil.ignore_patterns('.git','.textbook-agent','public','node_modules','.env','*.log','.hugo_build.lock'),symlinks=False)
    for slug,staged in staged_lessons.items():
        lesson=next(x for x in book.lessons if x.slug==slug)
        target=site/lesson_path(book,lesson).relative_to(book.output); target.parent.mkdir(parents=True,exist_ok=True)
        for p in staged.iterdir():
            if p.is_file() and not p.name.startswith('.') and p.suffix.lower() in ['.md','.png','.jpg','.jpeg','.svg','.webp','.gif']: shutil.copy2(p,target.parent/p.name)
    theme=None
    for config in configs:
        if config.suffix=='.toml': theme=tomllib.loads(config.read_text()).get('theme')
    if isinstance(theme,str) and not (site/'themes'/theme).exists():
        original=book.output.parent/theme
        if original.is_dir(): shutil.copytree(original,site/'themes'/theme,ignore=shutil.ignore_patterns('.git','node_modules','.env'))
        else: return ValidationResult(errors=['Hugo theme unavailable: '+theme],site_status='unavailable')
    try:
        p=subprocess.run(['hugo','--source',str(site),'--destination',str(public),'--cacheDir',str(work/'cache')],capture_output=True,text=True,timeout=120)
        (work/'build.log').write_text(p.stdout+'\n'+p.stderr,encoding='utf-8')
        if p.returncode: return ValidationResult(errors=['Hugo build failed; see staged site build.log'],site_status='failed')
        return ValidationResult(site_status='built',warnings=['Visually inspect representative Tamil text, diagrams, tables, and rendered formulas before student publication.'])
    except (OSError,subprocess.TimeoutExpired): return ValidationResult(errors=['Hugo build could not complete'],site_status='failed')
