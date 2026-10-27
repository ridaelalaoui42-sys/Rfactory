"""SQLite source, transcript and render-plan repository."""
import json,os,sqlite3
from pathlib import Path
from contextlib import contextmanager
from .core import SourceCreate,TranscriptItem,EditPlan

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
id INTEGER PRIMARY KEY, title TEXT NOT NULL, youtube_id TEXT,
local_file TEXT, rights TEXT NOT NULL, evidence TEXT NOT NULL,
attribution TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS transcripts (
id INTEGER PRIMARY KEY, source_id INTEGER NOT NULL REFERENCES sources(id),
start REAL NOT NULL, end REAL NOT NULL, text TEXT NOT NULL, language TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS transcript_time ON transcripts(source_id,start);
CREATE TABLE IF NOT EXISTS plans (
id INTEGER PRIMARY KEY, source_id INTEGER NOT NULL REFERENCES sources(id),
payload TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
result_file TEXT, error TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
"""

def db_path():return Path(os.getenv("CLIPFORGE_DB_PATH","./data/clipforge.sqlite3")).expanduser().resolve()
@contextmanager
def connect():
    path=db_path();path.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(str(path));db.row_factory=sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON");db.executescript(SCHEMA)
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback();raise
    finally:db.close()

def create_source(item:SourceCreate):
    with connect() as db:
        return db.execute("INSERT INTO sources(title,youtube_id,local_file,rights,evidence,attribution) VALUES(?,?,?,?,?,?)",
          (item.title,item.youtube_id,item.local_file,item.rights,item.evidence,item.attribution)).lastrowid

def source(source_id:int):
    with connect() as db:
        row=db.execute("SELECT * FROM sources WHERE id=?",(source_id,)).fetchone()
        return dict(row) if row else None

def sources():
    with connect() as db:
        return [dict(r) for r in db.execute("SELECT * FROM sources ORDER BY id DESC LIMIT 500")]

def import_transcript(source_id:int,items:list[TranscriptItem]):
    if not source(source_id):raise ValueError("Source not found")
    with connect() as db:
        db.executemany("INSERT INTO transcripts(source_id,start,end,text,language) VALUES(?,?,?,?,?)",
            [(source_id,x.start,x.end,x.text,x.language) for x in items])
    return len(items)

def search(query:str,limit:int=50):
    if not query.strip():return []
    with connect() as db:
        rows=db.execute("""SELECT t.source_id,s.title,s.youtube_id,t.start,t.end,t.text,t.language
        FROM transcripts t JOIN sources s ON s.id=t.source_id
        WHERE instr(lower(t.text), ?) > 0 ORDER BY t.source_id,t.start LIMIT ?""",
        (query.lower(),min(max(limit,1),100))).fetchall()
        return [dict(r) for r in rows]

def create_plan(plan:EditPlan):
    if not source(plan.source_id):raise ValueError("Source not found")
    with connect() as db:
        return db.execute("INSERT INTO plans(source_id,payload) VALUES(?,?)",
            (plan.source_id,plan.model_dump_json())).lastrowid

def plan(plan_id:int):
    with connect() as db:
        row=db.execute("SELECT * FROM plans WHERE id=?",(plan_id,)).fetchone()
    if not row:return None
    data=dict(row);data["payload"]=json.loads(data["payload"]);return data

def plan_status(plan_id:int,status:str,result_file=None,error=None):
    with connect() as db:
        db.execute("UPDATE plans SET status=?,result_file=?,error=? WHERE id=?",
            (status,result_file,error,plan_id))
