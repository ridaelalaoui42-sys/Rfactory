"""Safe private Editor V1 handoff. Never executes untrusted upstream installers."""
import json,os
from pathlib import Path
from .core import EditPlan

def status():
    raw=os.getenv("CLIPFORGE_EDITOR_V1_PATH","").strip()
    if not raw:return {"installed":False,"message":"Set CLIPFORGE_EDITOR_V1_PATH to private skill directory"}
    root=Path(raw).expanduser().resolve()
    skill=root/"SKILL.md"
    if not skill.is_file():return {"installed":False,"path":str(root),"message":"SKILL.md missing"}
    header=skill.read_text(encoding="utf-8",errors="replace")[:1000]
    ok="name: editor-v1" in header
    return {"installed":ok,"path":str(root),"message":
            "Upstream skill located; cinematic execution not yet wired" if ok else "Not Editor V1"}

def brief(plan:EditPlan,src:dict,out:Path):
    data={"style":"editor-v1","source_id":plan.source_id,
          "media":src["local_file"],"source_title":src["title"],
          "rights":src["rights"],"rights_evidence":src["evidence"],
          "format":plan.format,"project_title":plan.title,
          "ranges":[r.model_dump() for r in plan.ranges],
          "directions":["Preserve speaker meaning and argument completeness",
              "Only use authorized supplementary footage and music",
              "Generate accurate multilingual subtitles",
              "Use dynamic documentary editing without obscuring faces",
              "Ensure portrait AND landscape layout-specific typography",
              "Human-review sources and editorial quality before publishing"]}
    out.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding="utf-8")
    return out
