"""Durable, local SQLite job queue. One worker at a time per claimed job."""
import json,time
from . import storage
from .render import render
from .transcribe import transcribe

DDL="""CREATE TABLE IF NOT EXISTS jobs(
 id INTEGER PRIMARY KEY,kind TEXT NOT NULL,target_id INTEGER NOT NULL,
 status TEXT NOT NULL DEFAULT 'queued',attempts INTEGER NOT NULL DEFAULT 0,
 payload TEXT NOT NULL DEFAULT '{}',result TEXT,error TEXT,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
 CREATE INDEX IF NOT EXISTS ix_job_state ON jobs(status,id);"""

def init():
    with storage.connect() as db:db.executescript(DDL)

def enqueue(kind,target_id,payload=None):
    if kind not in ("render","transcribe") or target_id<1:raise ValueError("Invalid job")
    if kind=="render" and not storage.plan(target_id):raise ValueError("Unknown plan")
    if kind=="transcribe" and not storage.source(target_id):raise ValueError("Unknown source")
    init()
    with storage.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        existing=db.execute("SELECT id FROM jobs WHERE kind=? AND target_id=? AND status IN ('queued','running')",
                            (kind,target_id)).fetchone()
        if existing:return existing["id"]
        return db.execute("INSERT INTO jobs(kind,target_id,payload) VALUES(?,?,?)",
                          (kind,target_id,json.dumps(payload or {}))).lastrowid

def get(job_id):
    init()
    with storage.connect() as db:
        row=db.execute("SELECT * FROM jobs WHERE id=?",(job_id,)).fetchone()
    if not row:return None
    obj=dict(row);obj["payload"]=json.loads(obj["payload"])
    if obj["result"]:obj["result"]=json.loads(obj["result"])
    return obj

def all_jobs(limit=30):
    init()
    with storage.connect() as db:
        ids=[r["id"] for r in db.execute("SELECT id FROM jobs ORDER BY id DESC LIMIT ?",
                                        (max(1,min(limit,200)),))]
    return [get(i) for i in ids]

def claim():
    init()
    with storage.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row=db.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY id LIMIT 1").fetchone()
        if not row:return None
        db.execute("UPDATE jobs SET status='running',attempts=attempts+1,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                   (row["id"],))
        return dict(row)

def work_once():
    task=claim()
    if not task:return None
    try:
        if task["kind"]=="render":data=render(task["target_id"])
        else:data=transcribe(task["target_id"],**json.loads(task["payload"]))
        with storage.connect() as db:
            db.execute("UPDATE jobs SET status='complete',result=?,error=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                       (json.dumps(data),task["id"]))
    except Exception as exc:
        with storage.connect() as db:
            db.execute("UPDATE jobs SET status='failed',error=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                       (str(exc)[:1000],task["id"]))
    return get(task["id"])

def worker(once=False,interval=2.0):
    if once:return work_once()
    while True:
        if work_once() is None:time.sleep(interval)
