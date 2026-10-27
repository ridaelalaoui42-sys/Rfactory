"""CLI for research, editing plans and renders."""
import argparse,json
from pathlib import Path
from . import storage
from .core import SourceCreate,EditPlan,ClipRange
from .research import youtube_search,normalize_transcript
from .render import render
from .editorv1 import status

def main(argv=None):
    p=argparse.ArgumentParser(prog="clipforge")
    s=p.add_subparsers(dest="cmd",required=True)
    s.add_parser("init");s.add_parser("serve");s.add_parser("editor-v1-status")
    d=s.add_parser("discover");d.add_argument("--query",required=True);d.add_argument("--max-results",type=int,default=10)
    a=s.add_parser("add-source");a.add_argument("--title",required=True)
    a.add_argument("--local-file");a.add_argument("--youtube-id")
    a.add_argument("--rights",default="unknown");a.add_argument("--evidence",default="")
    a.add_argument("--attribution",default="")
    t=s.add_parser("import-transcript");t.add_argument("--source-id",type=int,required=True);t.add_argument("--json",required=True)
    q=s.add_parser("search-transcript");q.add_argument("--query",required=True)
    x=s.add_parser("create-plan");x.add_argument("--source-id",type=int,required=True)
    x.add_argument("--ranges",required=True,help="Comma-separated start:end seconds")
    x.add_argument("--format",choices=["vertical","horizontal","square"],required=True)
    x.add_argument("--output",required=True);x.add_argument("--title",default="")
    r=s.add_parser("render");r.add_argument("--plan-id",type=int,required=True)
    args=p.parse_args(argv)
    if args.cmd=="init":
        with storage.connect():pass
        print("Initialized",storage.db_path())
    elif args.cmd=="serve":
        import uvicorn
        uvicorn.run("clipforge.api:app",host="127.0.0.1",port=8000)
    elif args.cmd=="editor-v1-status":print(json.dumps(status(),indent=2))
    elif args.cmd=="discover":print(json.dumps(youtube_search(args.query,args.max_results),ensure_ascii=False,indent=2))
    elif args.cmd=="add-source":print(storage.create_source(SourceCreate(
        title=args.title,local_file=args.local_file,youtube_id=args.youtube_id,rights=args.rights,
        evidence=args.evidence,attribution=args.attribution)))
    elif args.cmd=="import-transcript":print(storage.import_transcript(args.source_id,
        normalize_transcript(json.loads(Path(args.json).read_text(encoding="utf-8")))))
    elif args.cmd=="search-transcript":print(json.dumps(storage.search(args.query),ensure_ascii=False,indent=2))
    elif args.cmd=="create-plan":
        ranges=[ClipRange(start=float(a),end=float(b)) for a,b in
                (part.split(":") for part in args.ranges.split(","))]
        print(storage.create_plan(EditPlan(source_id=args.source_id,ranges=ranges,
              format=args.format,output_name=args.output,title=args.title)))
    elif args.cmd=="render":print(json.dumps(render(args.plan_id),indent=2))

if __name__=="__main__":main()
