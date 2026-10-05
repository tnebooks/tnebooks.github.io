import argparse,json,sys
from pathlib import Path
from .config import load_manifest,resolve_book
from .models import RunLimits
from .paths import checked_path
from .state import load_state
from .pipeline import run_book
from .api import AgentError

def main(argv=None):
    parser=argparse.ArgumentParser(prog='textbook-agent',description='Create or repair English/Tamil school textbook lessons from PDF sources.')
    subs=parser.add_subparsers(dest='command',required=True)
    for command in ['run','audit']:
        p=subs.add_parser(command)
        p.add_argument('--manifest',type=Path); p.add_argument('--book')
        p.add_argument('--pdf',type=Path); p.add_argument('--output',type=Path,default=Path.cwd())
        p.add_argument('--medium',choices=['en','ta']); p.add_argument('--class',dest='class_name'); p.add_argument('--subject'); p.add_argument('--edition'); p.add_argument('--term'); p.add_argument('--volume'); p.add_argument('--model')
        p.add_argument('--lesson',action='append'); p.add_argument('--force',action='store_true')
        limits_arguments(p)
    p=subs.add_parser('resume'); p.add_argument('--run',required=True); p.add_argument('--output',type=Path,default=Path.cwd()); p.add_argument('--token-limit',type=int); p.add_argument('--max-seconds',type=float)
    p=subs.add_parser('status'); p.add_argument('--run'); p.add_argument('--output',type=Path,default=Path.cwd())
    args=parser.parse_args(argv)
    try:
        root=checked_path(args.output.expanduser().resolve(),'.textbook-agent')
        if args.command=='status':
            states=[load_state(root,args.run)] if args.run else [load_state(root,p.parent.name) for p in sorted((root/'runs').glob('*/state.json'))]
            if not states: print('No saved runs.')
            for state in states: print(json.dumps({'run':state.id,'book':state.book.book_id,'status':state.status,'elapsed_seconds':state.elapsed,'lessons':{k:r.get('status') for k,r in state.lessons.items()}},ensure_ascii=False,indent=2))
            return 0
        selected=None
        if args.command=='resume':
            saved=load_state(root,args.run); book=resolve_book(saved.book.model_dump()); limits=saved.limits
            if args.token_limit is not None: limits.token_limit=args.token_limit
            if args.max_seconds is not None: limits.max_seconds=args.max_seconds
            state=run_book(book,limits,saved.mode,run_id=saved.id)
        else:
            if args.manifest: book=load_manifest(args.manifest.expanduser().resolve())
            elif args.book: book=load_manifest(checked_path(root,f'books/{args.book}.json'))
            else:
                required=['pdf','medium','class_name','subject','edition']
                if any(getattr(args,k) is None for k in required): raise ValueError('Provide --manifest, --book, or --pdf --medium --class --subject --edition')
                import re
                identifier=re.sub(r'[^a-z0-9]+','-',f'class-{args.class_name}-{args.subject}-{args.medium}-{args.edition}-{args.term or ""}-{args.volume or ""}'.lower()).strip('-')
                book=resolve_book({'book_id':identifier,**{k:getattr(args,k) for k in ['pdf','output','medium','class_name','subject','edition','term','volume','model']}})
            if args.manifest or args.book:
                if args.model: book=resolve_book({**book.model_dump(),'model':args.model})
                if args.output!=Path.cwd(): book.output=args.output.expanduser().resolve()
            selected=set(args.lesson or [])
            if book.lessons and selected and not selected<={x.id for x in book.lessons}|{x.slug for x in book.lessons}: raise ValueError('Unknown selected lesson ID or slug')
            limits=RunLimits(page_window=args.pages_per_call,timeout=args.timeout,max_output_tokens=args.max_output_tokens,max_calls_per_lesson=args.max_calls_per_lesson,token_limit=args.token_limit,max_seconds=args.max_seconds)
            state=run_book(book,limits,args.command,force=args.force,selected_ids=selected)
        return 0 if state.status=='complete' else 1 if state.status=='interrupted' else 2
    except (ValueError,OSError,AgentError) as exc:
        print('textbook-agent: '+str(exc),file=sys.stderr); return 1

def limits_arguments(p):
    p.add_argument('--pages-per-call',type=int,default=2)
    p.add_argument('--timeout',type=float,default=120)
    p.add_argument('--max-output-tokens',type=int,default=8192)
    p.add_argument('--max-calls-per-lesson',type=int,default=100)
    p.add_argument('--token-limit',type=int)
    p.add_argument('--max-seconds',type=float)

if __name__=='__main__': raise SystemExit(main())
