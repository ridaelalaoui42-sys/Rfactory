"""Worker entrypoint for Docker and process managers."""
import argparse
from .jobs import worker, fail_stale_jobs

def main():
    parser=argparse.ArgumentParser(description="ClipForge render/transcription worker")
    parser.add_argument("--once",action="store_true")
    args=parser.parse_args()
    fail_stale_jobs()
    job=worker(once=args.once)
    if args.once:print(job)

if __name__=="__main__":main()
