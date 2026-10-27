"""Prepare an original, privately installed Editor V1 workspace.

This runs a trusted operator-installed upstream project bootstrap, not a cinematic
edit and not a third-party installer. No skill files are redistributed.
"""
import os,re,subprocess
from pathlib import Path
from . import storage
from .editorv1 import status
from .render import output_root

def prepare(plan_id:int)->dict:
    info=status()
    if not info["installed"]:
        raise RuntimeError("Original Editor V1 skill not available at CLIPFORGE_EDITOR_V1_PATH")
    record=storage.plan(plan_id)
    if not record or record["status"]!="complete":
        raise ValueError("Complete the ClipForge rough cut before preparing Editor V1")
    if record["payload"]["format"]!="horizontal":
        raise ValueError("Original Editor V1 bootstrap is 16:9 only; portrait execution needs layout adaptation")
    root=Path(info["path"])
    script=root/"scripts"/"new-video.sh"
    if not script.is_file():
        raise RuntimeError("Original Editor V1 new-video.sh missing")
    file=Path(record["result_file"]).resolve()
    if not file.is_relative_to(output_root()) or not file.is_file():
        raise ValueError("Video output no longer exists")
    parent=output_root()/"editor-v1-projects"
    parent.mkdir(parents=True,exist_ok=True)
    name="clipforge-plan-"+str(plan_id)
    destination=parent/name
    if destination.exists():
        return {"plan_id":plan_id,"project":str(destination),"existing":True}
    # This script is exclusively from the operator-approved, privately installed skill.
    process=subprocess.run(["bash",str(script),str(file),name,"--dir",str(parent)],
                           capture_output=True,text=True,timeout=1200,check=False)
    if process.returncode:
        raise RuntimeError("Editor V1 project bootstrap failed: "+process.stderr[-900:])
    return {"plan_id":plan_id,"project":str(destination),"existing":False,
            "note":"Edit PLAN.md and build.py using private Editor V1 instructions; no cinematic render executed"}
