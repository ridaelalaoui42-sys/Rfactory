#!/usr/bin/env python3
"""Standalone Rfactory render worker for a single-PC/VM SQLite deployment.

The API can enqueue jobs; this persistent process renders them. A local
advisory lock prevents two workers on the same host/storage directory from
claiming the same queued job. NOT a multi-host PostgreSQL leasing system.
No browser publishing or Gemini credentials needed.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import signal
import sys
import time

from scripts.bootstrap_factory import bootstrap
from services.content.agent import ContentGenerationAgent
from services.engine.renderer import PuzzleVideoRenderer
from services.worker.batch_runner import BatchProductionWorker

ROOT=Path(__file__).resolve().parents[1]
STOP=False


class WorkerLock:
    def __init__(self,path:Path):
        self.path=path
        self.handle=None

    def __enter__(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        handle=self.path.open("a+b")
        try:
            if os.name=="nt":
                import msvcrt
                handle.seek(0)
                # Lock one byte; ensure it exists on a new lock file.
                if handle.seek(0,2)==0:
                    handle.write(b"0")
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except (OSError,BlockingIOError):
            handle.close()
            raise RuntimeError("Another Rfactory render worker owns the local queue lock")
        self.handle=handle
        return self

    def __exit__(self,exc_type,exc,tb):
        if self.handle is not None:
            try:
                if os.name=="nt":
                    import msvcrt
                    self.handle.seek(0)
                    msvcrt.locking(self.handle.fileno(),msvcrt.LK_UNLCK,1)
                else:
                    import fcntl
                    fcntl.flock(self.handle.fileno(),fcntl.LOCK_UN)
            finally:
                self.handle.close()
                self.handle=None


def stop_handler(signum,frame):
    global STOP
    STOP=True


def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--once",action="store_true",help="Process queued jobs then exit")
    parser.add_argument("--poll-seconds",type=float,default=4.0)
    parser.add_argument("--max-jobs",type=int,default=0,
                        help="Optional total job limit; zero means unlimited")
    args=parser.parse_args()
    if not 0.5<=args.poll_seconds<=3600:
        parser.error("--poll-seconds must be 0.5 to 3600")
    if args.max_jobs<0:
        parser.error("--max-jobs must be non-negative")
    signal.signal(signal.SIGINT,stop_handler)
    if hasattr(signal,"SIGTERM"):
        signal.signal(signal.SIGTERM,stop_handler)
    storage=ROOT/"storage"
    processed=0
    with WorkerLock(storage/"runtime"/"render_worker.lock"):
        repo=bootstrap()
        engine=PuzzleVideoRenderer(storage/"assets",storage/"renders")
        worker=BatchProductionWorker(repo,engine,ContentGenerationAgent(),
                                     worker_id=f"local_{os.getpid()}")
        print(f"Rfactory worker PID {os.getpid()} ready. Publishing disabled.",flush=True)
        while not STOP:
            if args.max_jobs and processed>=args.max_jobs:
                break
            try:
                result=worker.process_all_queued_jobs(limit=1)
            except Exception as exc:
                print(f"Worker queue error: {type(exc).__name__}: {exc}",file=sys.stderr,flush=True)
                # Do not loop rapidly on an unavailable database.
                if args.once:
                    return 1
                time.sleep(args.poll_seconds)
                continue
            if result:
                processed+=len(result)
                for item in result:
                    print(f"{item.get('job_id')}: {item.get('status')}",flush=True)
            elif args.once:
                break
            else:
                time.sleep(args.poll_seconds)
        print(f"Rfactory worker stopped; jobs processed: {processed}",flush=True)
    return 0


if __name__=="__main__":
    sys.exit(main())
