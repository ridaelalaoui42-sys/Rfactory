"""SQLite-backed durable single-host queue for approved library-to-Reel renders.

Atomic claims, retryable expired leases, progress and approval-state checks.
Designed for one persistent Rfactory VM/PC and its shared storage volume,
NOT advertised as a distributed PostgreSQL queue.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import re
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Callable

from services.assets.library import AssetLibrary, LibraryError
from scripts.render_from_library import render_approved_asset

JOB_RE=re.compile(r"^ajob_[a-f0-9]{24}$")
IDEMPOTENCY_RE=re.compile(r"^[a-zA-Z0-9._:-]{8,120}$")
LEASE_SECONDS=900


def utc_now()->str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class RenderQueue:
    def __init__(self, storage_root: Path):
        self.storage=Path(storage_root)
        self.storage.mkdir(parents=True,exist_ok=True)
        self.db_path=self.storage/"factory.db"
        self._migrate()

    def _conn(self)->sqlite3.Connection:
        c=sqlite3.connect(str(self.db_path),timeout=30.0)
        c.row_factory=sqlite3.Row
        c.execute("PRAGMA busy_timeout=30000")
        c.execute("PRAGMA journal_mode=WAL")
        return c

    def _migrate(self)->None:
        with self._conn() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS art_render_jobs (
              id TEXT PRIMARY KEY,
              idempotency_key TEXT UNIQUE,
              request_json TEXT NOT NULL,
              status TEXT NOT NULL CHECK(status IN ('QUEUED','RUNNING','READY','FAILED','CANCELLED')),
              progress_pct INTEGER NOT NULL DEFAULT 0,
              attempts INTEGER NOT NULL DEFAULT 0,
              max_attempts INTEGER NOT NULL DEFAULT 2,
              worker_id TEXT,
              lease_until TEXT,
              last_error TEXT,
              result_json TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              completed_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_art_render_queue
              ON art_render_jobs(status,created_at);
            """)

    @staticmethod
    def _public(row: sqlite3.Row | dict)->dict:
        r=dict(row)
        r.pop("request_json",None)
        r.pop("result_json",None)
        r.pop("idempotency_key",None)
        result=json.loads(row["result_json"]) if row["result_json"] else None
        return {
            "id":r["id"],"status":r["status"],
            "progress_pct":r["progress_pct"],
            "attempts":r["attempts"],
            "max_attempts":r["max_attempts"],
            "created_at":r["created_at"],"updated_at":r["updated_at"],
            "completed_at":r["completed_at"],
            "error":r["last_error"] if r["status"]=="FAILED" else None,
            "result":result if r["status"]=="READY" else None,
        }

    def enqueue(self,request:dict[str,Any],idempotency_key:str|None=None)->dict:
        if idempotency_key and not IDEMPOTENCY_RE.fullmatch(idempotency_key):
            raise ValueError("Idempotency key must be 8-120 safe ASCII characters")
        # Canonicalized JSON + equivalence protects against accidental reuse
        # of a client idempotency key for a different video.
        payload=json.dumps(request,sort_keys=True,separators=(",",":"))
        now=utc_now()
        job_id="ajob_"+uuid.uuid4().hex[:24]
        with self._conn() as c:
            c.execute("BEGIN IMMEDIATE")
            if idempotency_key:
                prior=c.execute("SELECT * FROM art_render_jobs WHERE idempotency_key=?",
                                (idempotency_key,)).fetchone()
                if prior:
                    if prior["request_json"]!=payload:
                        raise ValueError("Idempotency key already used with another render specification")
                    return self._public(prior)
            c.execute("""INSERT INTO art_render_jobs
                (id,idempotency_key,request_json,status,progress_pct,attempts,
                 max_attempts,created_at,updated_at)
                VALUES (?, ?, ?, 'QUEUED', 0, 0, 2, ?, ?)""",
                (job_id,idempotency_key,payload,now,now))
            return self._public(c.execute("SELECT * FROM art_render_jobs WHERE id=?",
                                          (job_id,)).fetchone())

    def get(self,job_id:str)->dict:
        if not JOB_RE.fullmatch(job_id):
            raise KeyError("Invalid job ID")
        with self._conn() as c:
            row=c.execute("SELECT * FROM art_render_jobs WHERE id=?",(job_id,)).fetchone()
        if row is None:
            raise KeyError("Job not found")
        return self._public(row)

    def list(self,limit:int=25)->list[dict]:
        if not 1<=limit<=100:
            raise ValueError("Queue page limit must be 1-100")
        with self._conn() as c:
            rows=c.execute("SELECT * FROM art_render_jobs ORDER BY created_at DESC,id DESC LIMIT ?",
                           (limit,)).fetchall()
        return [self._public(row) for row in rows]

    def cancel(self,job_id:str)->dict:
        if not JOB_RE.fullmatch(job_id):
            raise KeyError("Invalid job ID")
        now=utc_now()
        with self._conn() as c:
            c.execute("BEGIN IMMEDIATE")
            row=c.execute("SELECT * FROM art_render_jobs WHERE id=?",(job_id,)).fetchone()
            if not row:
                raise KeyError("Job not found")
            if row["status"] not in ("QUEUED","FAILED"):
                raise ValueError("Only queued/failed jobs can be cancelled; a running FFmpeg render cannot be safely interrupted yet")
            c.execute("UPDATE art_render_jobs SET status='CANCELLED',updated_at=?,completed_at=? WHERE id=?",
                      (now,now,job_id))
            return self._public(c.execute("SELECT * FROM art_render_jobs WHERE id=?",
                                          (job_id,)).fetchone())

    def retry(self,job_id:str)->dict:
        if not JOB_RE.fullmatch(job_id):
            raise KeyError("Invalid job ID")
        now=utc_now()
        with self._conn() as c:
            c.execute("BEGIN IMMEDIATE")
            row=c.execute("SELECT * FROM art_render_jobs WHERE id=?",(job_id,)).fetchone()
            if not row:
                raise KeyError("Job not found")
            if row["status"] not in ("FAILED","CANCELLED"):
                raise ValueError("Only failed or cancelled jobs can be requeued")
            c.execute("""UPDATE art_render_jobs SET status='QUEUED',progress_pct=0,
                        attempts=0,worker_id=NULL,lease_until=NULL,
                        last_error=NULL,completed_at=NULL,updated_at=?
                        WHERE id=?""",(now,job_id))
            return self._public(c.execute("SELECT * FROM art_render_jobs WHERE id=?",
                                          (job_id,)).fetchone())

    def recover_expired(self)->dict[str,int]:
        now=utc_now()
        with self._conn() as c:
            c.execute("BEGIN IMMEDIATE")
            retry=c.execute("""UPDATE art_render_jobs
                SET status='QUEUED',progress_pct=0,worker_id=NULL,lease_until=NULL,
                    updated_at=?, last_error='Worker lease expired; retrying'
                WHERE status='RUNNING' AND lease_until < ?
                      AND attempts < max_attempts""",(now,now)).rowcount
            fail=c.execute("""UPDATE art_render_jobs
                SET status='FAILED',worker_id=NULL,lease_until=NULL,updated_at=?,
                    completed_at=?,last_error='Worker lease expired; retries exhausted'
                WHERE status='RUNNING' AND lease_until < ?
                      AND attempts >= max_attempts""",(now,now,now)).rowcount
        return {"requeued":retry,"failed":fail}

    def claim(self,worker_id:str)->tuple[str,dict]|None:
        if not isinstance(worker_id,str) or not re.fullmatch(r"[a-zA-Z0-9_-]{3,80}",worker_id):
            raise ValueError("Invalid worker identifier")
        now=utc_now()
        lease=(datetime.now(timezone.utc)+timedelta(seconds=LEASE_SECONDS)).isoformat(timespec="seconds")
        with self._conn() as c:
            c.execute("BEGIN IMMEDIATE")
            row=c.execute("""SELECT id,request_json FROM art_render_jobs
                WHERE status='QUEUED' ORDER BY created_at,id LIMIT 1""").fetchone()
            if row is None:
                return None
            c.execute("""UPDATE art_render_jobs SET status='RUNNING',attempts=attempts+1,
                worker_id=?,lease_until=?,progress_pct=1,updated_at=?
                WHERE id=? AND status='QUEUED'""",(worker_id,lease,now,row["id"]))
            return row["id"],json.loads(row["request_json"])

    def progress(self,job_id:str,worker_id:str,pct:int)->None:
        pct=max(1,min(95,int(pct)))
        now=utc_now()
        lease=(datetime.now(timezone.utc)+timedelta(seconds=LEASE_SECONDS)).isoformat(timespec="seconds")
        with self._conn() as c:
            c.execute("""UPDATE art_render_jobs SET progress_pct=max(progress_pct,?),
                lease_until=?,updated_at=? WHERE id=? AND worker_id=? AND status='RUNNING'""",
                (pct,lease,now,job_id,worker_id))

    def complete(self,job_id:str,worker_id:str,result:dict)->None:
        now=utc_now()
        # Store only safe public fields. Absolute VM paths must not be exposed.
        video_id=Path(result["video"]).parent.name
        if not re.fullmatch(r"library_[a-f0-9]{14}",video_id):
            raise ValueError("Unexpected local video render identifier")
        public={
            "id":video_id,
            "video_url":f"/api/v1/library/renders/{video_id}/video",
            "report_url":f"/api/v1/library/renders/{video_id}/report",
            "exact_fit_times_sec":result["exact_fit_times_sec"],
            "decoded_frames_checked":result["all_frames_checked"],
            "raw_alignment_mad":result["raw_alignment_mad"],
            "source_provenance":result["source_provenance"],
            "fallback_used":result["explicit_fallback"],
            "face_mode":result.get("face_mode"),
            "reviewed_cutout_pack_id":result.get("reviewed_cutout_pack_id"),
            "published":False,
        }
        with self._conn() as c:
            updated=c.execute("""UPDATE art_render_jobs
                SET status='READY',progress_pct=100,result_json=?,last_error=NULL,
                    lease_until=NULL,completed_at=?,updated_at=?
                WHERE id=? AND worker_id=? AND status='RUNNING'""",
                (json.dumps(public),now,now,job_id,worker_id)).rowcount
            if updated!=1:
                raise RuntimeError("Render completion rejected because lease owner changed")

    def fail(self,job_id:str,worker_id:str,error:str)->None:
        now=utc_now()
        # Do not persist provider exception text or secrets/stack traces.
        safe=str(error)[:160]
        with self._conn() as c:
            c.execute("""UPDATE art_render_jobs
                SET status='FAILED',lease_until=NULL,updated_at=?,
                completed_at=?,last_error=? WHERE id=? AND worker_id=? AND status='RUNNING'""",
                (now,now,safe,job_id,worker_id))

    def process_one(self,worker_id:str)->dict|None:
        self.recover_expired()
        claim=self.claim(worker_id)
        if claim is None:
            return None
        job_id,request=claim
        # Must continue validating approval and original source integrity at
        # EXECUTION time; the artwork can change after enqueue.
        try:
            kwargs=dict(request)
            original=kwargs.pop("asset_id")
            cfg={
                "storage_root":self.storage,
                "allow_fallback":kwargs.pop("allow_fallback",False),
                "geometry":kwargs.pop("geometry","organic"),
                "motion":kwargs.pop("motion_profile","orbit_lock"),
                "duration":kwargs.pop("duration_sec",12),
                "crossings":kwargs.pop("exact_fit_count",5),
                "seed":kwargs.pop("seed",42041),
                "enable_sfx":kwargs.pop("enable_sfx",True),
                "face_mode":kwargs.pop("face_mode",""),
                "subject_type":kwargs.pop("subject_type","animal"),
                "face_bbox_norm":kwargs.pop("face_bbox_norm",None),
                "face_asset_seed":kwargs.pop("face_asset_seed",None),
                "face_pack_id":kwargs.pop("face_pack_id",""),
            }
            if kwargs:
                raise ValueError("Unknown or unsupported render specification")
            def on_frame(done:int,total:int):
                self.progress(job_id,worker_id,int(5+80*done/max(total,1)))
            report=render_approved_asset(original,progress_callback=on_frame,**cfg)
            self.complete(job_id,worker_id,report)
        except Exception:
            # Avoid exposing private filepaths, user assets or API credentials
            # through status polling. Full tracebacks remain in worker logs.
            self.fail(job_id,worker_id,"Render or QA failed; inspect private worker logs")
        return self.get(job_id)
