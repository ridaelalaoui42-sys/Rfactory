"""Scheduled, deduplicated YouTube metadata research by saved topic.

Official Data API search only. Public videos discovered here remain research
candidates, never automatically approved footage.
"""
import os,re
from . import storage
from .research import youtube_search

DDL="""CREATE TABLE IF NOT EXISTS topic_watches(
 id INTEGER PRIMARY KEY,query TEXT NOT NULL,region TEXT NOT NULL,
 language TEXT NOT NULL,interval_hours INTEGER NOT NULL DEFAULT 24,
 enabled INTEGER NOT NULL DEFAULT 1,
 next_scan TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 last_scan TEXT,last_error TEXT);
CREATE TABLE IF NOT EXISTS topic_results(
 topic_id INTEGER NOT NULL REFERENCES topic_watches(id),
 video_id TEXT NOT NULL,title TEXT NOT NULL,channel TEXT NOT NULL,
 published_at TEXT,first_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(topic_id,video_id));
CREATE TABLE IF NOT EXISTS discovery_events(
 id INTEGER PRIMARY KEY,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS idx_topics_scan ON topic_watches(enabled,next_scan);"""

def init():
    with storage.connect() as db:db.executescript(DDL)

def create(query:str,region:str="MA",language:str="ar",interval_hours:int=24):
    if not query.strip() or len(query)>160:raise ValueError("Topic must be 1–160 characters")
    if not re.fullmatch("[A-Z]{2}",region):raise ValueError("Use ISO country code")
    if not re.fullmatch("[a-z]{2,3}",language):raise ValueError("Invalid language code")
    if not 6<=interval_hours<=168:raise ValueError("Interval must be 6–168 hours")
    init()
    with storage.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        count=db.execute("SELECT COUNT(*) AS n FROM topic_watches").fetchone()["n"]
        if count>=12:raise ValueError("12 topic watches maximum")
        return db.execute("""INSERT INTO topic_watches(query,region,language,interval_hours)
                         VALUES(?,?,?,?)""",(query.strip(),region,language,interval_hours)).lastrowid

def watches():
    init()
    with storage.connect() as db:
        return [dict(x) for x in db.execute("SELECT * FROM topic_watches ORDER BY id DESC")]

def results(topic_id:int|None=None,limit:int=100):
    init()
    with storage.connect() as db:
        if topic_id:
            rows=db.execute("""SELECT * FROM topic_results WHERE topic_id=?
                           ORDER BY first_seen DESC LIMIT ?""",(topic_id,min(max(1,limit),200)))
        else:
            rows=db.execute("""SELECT * FROM topic_results
                           ORDER BY first_seen DESC LIMIT ?""",(min(max(1,limit),200),))
        return [dict(x) for x in rows]

def scan(topic_id:int):
    init()
    if not os.getenv("YOUTUBE_API_KEY"):raise ValueError("YOUTUBE_API_KEY is required for scheduled research")
    with storage.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row=db.execute("SELECT * FROM topic_watches WHERE id=?",(topic_id,)).fetchone()
        if not row:raise ValueError("Topic watch does not exist")
        cap=int(os.getenv("CLIPFORGE_DISCOVERY_MAX_QUERIES_PER_DAY","20"))
        used=db.execute("""SELECT COUNT(*) AS n FROM discovery_events
                       WHERE created_at>=datetime('now','-1 day')""").fetchone()["n"]
        if used>=max(1,min(cap,100)):
            raise ValueError("Research API daily safety budget exceeded")
        db.execute("INSERT INTO discovery_events DEFAULT VALUES")
        db.execute("""UPDATE topic_watches SET next_scan=datetime('now',?)
                      WHERE id=?""",(f"+{row['interval_hours']} hours",topic_id))
        config=dict(row)
    try:
        discovered=youtube_search(config["query"],max_results=10,
                                  region_code=config["region"],language=config["language"])
        with storage.connect() as db:
            for item in discovered:
                db.execute("""INSERT OR IGNORE INTO topic_results
                (topic_id,video_id,title,channel,published_at) VALUES(?,?,?,?,?)""",
                (topic_id,item["youtube_id"],item["title"],item["channel"],item["published_at"]))
            db.execute("""UPDATE topic_watches SET last_scan=CURRENT_TIMESTAMP,last_error=NULL
                          WHERE id=?""",(topic_id,))
        return {"topic_id":topic_id,"found":len(discovered)}
    except Exception as exc:
        with storage.connect() as db:
            db.execute("UPDATE topic_watches SET last_error=? WHERE id=?",
                       (str(exc)[:600],topic_id))
        raise

def scan_due(limit:int=2):
    if not os.getenv("YOUTUBE_API_KEY"):return []
    init()
    with storage.connect() as db:
        cap=int(os.getenv("CLIPFORGE_DISCOVERY_MAX_QUERIES_PER_DAY","20"))
        used=db.execute("SELECT COUNT(*) AS n FROM discovery_events WHERE created_at>=datetime('now','-1 day')").fetchone()["n"]
        if used>=max(1,min(cap,100)):return []
        ids=[r["id"] for r in db.execute("""SELECT id FROM topic_watches
            WHERE enabled=1 AND next_scan <= CURRENT_TIMESTAMP
            ORDER BY next_scan LIMIT ?""",(max(1,min(4,limit)),))]
    out=[]
    for topic_id in ids:
        try:out.append(scan(topic_id))
        except Exception as exc:out.append({"topic_id":topic_id,"error":str(exc)[:200]})
    return out
