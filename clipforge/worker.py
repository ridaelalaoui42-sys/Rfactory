"""Worker entrypoint for Docker and process managers."""
import argparse
from .jobs import worker

def main():
    parser=argparse.ArgumentParser(description="ClipForge render/transcription worker")
    parser.add_argument("--once",action="store_true")
    args=parser.parse_args()
    job=worker(once=args.once)
    if args.once:print(job)

if __name__=="__main__":main()
