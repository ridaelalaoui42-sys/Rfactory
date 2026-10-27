"""ClipForge processing and scheduled topic research worker."""
import argparse,logging,time
from . import jobs,topics

logger=logging.getLogger("clipforge.worker")

def main():
    parser=argparse.ArgumentParser(description="ClipForge jobs and scheduled discovery")
    parser.add_argument("--once",action="store_true")
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    jobs.fail_stale_jobs()
    if args.once:
        print({"topics":topics.scan_due(),"job":jobs.work_once()})
        return
    while True:
        try:
            scans=topics.scan_due(limit=1)
            if scans:logger.info("Topic scan results: %s",scans)
        except Exception as exc:
            logger.error("Discovery scheduler failed: %s",exc)
        if jobs.work_once() is None:time.sleep(2)

if __name__=="__main__":main()
