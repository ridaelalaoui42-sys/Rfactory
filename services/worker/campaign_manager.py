"""Atomic campaign submission and progress summaries over the existing queue.

One SQLite IMMEDIATE transaction creates the campaign and *all* constituent
jobs or none. This prevents partial campaigns, double submissions and silent
duplicate work when the Studio reconnects.
"""
from __future__ import annotations

import json
import re
import sqlite3
import uuid
from typing import Any

from services.worker.art_render_queue import RenderQueue, JOB_RE, IDEMPOTENCY_RE, utc_now

CAMPAIGN_RE = re.compile(r"^camp_[a-f0-9]{24}$")


class CampaignManager:
    def __init__(self, queue: RenderQueue):
        self.queue=queue
        self._migrate()

    def _migrate(self)->None:
        with self.queue._conn() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS art_campaigns (
              id TEXT PRIMARY KEY,
              idempotency_key TEXT UNIQUE,
              request_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              name TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS art_campaign_items (
              campaign_id TEXT NOT NULL REFERENCES art_campaigns(id),
              job_id TEXT UNIQUE NOT NULL REFERENCES art_render_jobs(id),
              position INTEGER NOT NULL,
              PRIMARY KEY(campaign_id,position)
            );
            CREATE INDEX IF NOT EXISTS idx_art_campaign_items_job
              ON art_campaign_items(job_id);
            """)

    def create(
        self, name: str, request: dict[str, Any],
        validated_specs: list[dict[str,Any]],
        idempotency_key: str | None = None,
    )->dict:
        if not isinstance(name,str) or not 2<=len(name.strip())<=90:
            raise ValueError("Campaign name must be 2–90 characters")
        if not 2<=len(validated_specs)<=24:
            raise ValueError("Create 2–24 jobs in one campaign")
        if idempotency_key is not None and not IDEMPOTENCY_RE.fullmatch(idempotency_key):
            raise ValueError("Campaign idempotency key must be 8–120 safe characters")
        if not isinstance(request,dict):
            raise ValueError("Campaign request must be a dictionary")
        normalized=json.dumps(request,sort_keys=True,separators=(",",":"),allow_nan=False)
        prepared=[json.dumps(p,sort_keys=True,separators=(",",":"),allow_nan=False)
                  for p in validated_specs]
        campaign_id="camp_"+uuid.uuid4().hex[:24]
        now=utc_now()
        with self.queue._conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if idempotency_key:
                previous=conn.execute("SELECT id,request_json FROM art_campaigns WHERE idempotency_key=?",
                                      (idempotency_key,)).fetchone()
                if previous:
                    if previous["request_json"]!=normalized:
                        raise ValueError("Campaign idempotency key reused with different parameters")
                    campaign_id=previous["id"]
                    return self._get_with_connection(conn,campaign_id)
            conn.execute("INSERT INTO art_campaigns (id,idempotency_key,request_json,created_at,name) VALUES (?,?,?,?,?)",
                         (campaign_id,idempotency_key,normalized,now,name.strip()))
            for i,payload in enumerate(prepared):
                job_id="ajob_"+uuid.uuid4().hex[:24]
                conn.execute("""INSERT INTO art_render_jobs
                    (id,idempotency_key,request_json,status,progress_pct,attempts,
                     max_attempts,created_at,updated_at)
                    VALUES (?,NULL,?,'QUEUED',0,0,2,?,?)""",
                    (job_id,payload,now,now))
                conn.execute("""INSERT INTO art_campaign_items
                    (campaign_id,job_id,position) VALUES (?,?,?)""",
                    (campaign_id,job_id,i))
            return self._get_with_connection(conn,campaign_id)

    def _get_with_connection(self,conn:sqlite3.Connection,campaign_id:str)->dict:
        campaign=conn.execute(
            "SELECT id,name,created_at FROM art_campaigns WHERE id=?",(campaign_id,)
        ).fetchone()
        if not campaign:
            raise KeyError("Campaign not found")
        rows=conn.execute("""
          SELECT j.* , ci.position
          FROM art_campaign_items ci
          JOIN art_render_jobs j ON j.id=ci.job_id
          WHERE ci.campaign_id=?
          ORDER BY ci.position
        """,(campaign_id,)).fetchall()
        jobs=[self.queue._public(row) for row in rows]
        counts={state:sum(x["status"]==state for x in jobs)
                for state in ("QUEUED","RUNNING","READY","FAILED","CANCELLED")}
        total=len(jobs)
        active=counts["RUNNING"]+counts["QUEUED"]
        if active:
            state="RUNNING" if counts["RUNNING"] else "QUEUED"
        elif counts["FAILED"]:
            state="PARTIAL" if counts["READY"] else "FAILED"
        elif counts["CANCELLED"]:
            state="PARTIAL" if counts["READY"] else "CANCELLED"
        else:
            state="READY"
        return {
            "id":campaign["id"],"name":campaign["name"],
            "created_at":campaign["created_at"],
            "status":state, "total":total,
            "counts":counts,
            "progress_pct":round(sum(job["progress_pct"] for job in jobs)/total) if total else 0,
            "jobs":jobs,
            "published":False,
        }

    def get(self,campaign_id:str)->dict:
        if not CAMPAIGN_RE.fullmatch(campaign_id):
            raise KeyError("Invalid campaign ID")
        with self.queue._conn() as conn:
            return self._get_with_connection(conn,campaign_id)

    def list(self,limit:int=12)->list[dict]:
        if not 1<=limit<=50:
            raise ValueError("Campaign limit must be 1–50")
        with self.queue._conn() as conn:
            ids=conn.execute("SELECT id FROM art_campaigns ORDER BY created_at DESC,id DESC LIMIT ?",(limit,)).fetchall()
            return [self._get_with_connection(conn,row["id"]) for row in ids]

    def cancel_pending(self,campaign_id:str)->dict:
        if not CAMPAIGN_RE.fullmatch(campaign_id):
            raise KeyError("Invalid campaign ID")
        now=utc_now()
        with self.queue._conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if not conn.execute("SELECT 1 FROM art_campaigns WHERE id=?",(campaign_id,)).fetchone():
                raise KeyError("Campaign not found")
            conn.execute("""
              UPDATE art_render_jobs SET status='CANCELLED',
              completed_at=?,updated_at=?
              WHERE status='QUEUED' AND id IN (
                SELECT job_id FROM art_campaign_items WHERE campaign_id=?
              )
            """,(now,now,campaign_id))
            return self._get_with_connection(conn,campaign_id)
