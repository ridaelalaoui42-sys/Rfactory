"""Import ChatGPT-generated or user-curated Rfactory image ZIPs locally.

python -m scripts.import_asset_pack /path/to/Rfactory_Asset_Library_v1.zip

Images remain AWAITING_REVIEW or REFERENCE_ONLY, never auto-approved.
No provider credentials, cloud upload or automatic publishing required.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from services.assets.library import AssetLibrary, LibraryError

ROOT=Path(__file__).resolve().parents[1]


def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("archive",type=Path,help="Rfactory Asset Library ZIP")
    parser.add_argument("--storage-root",type=Path,default=ROOT/"storage")
    args=parser.parse_args()
    if not args.archive.is_file():
        parser.error("Asset pack not found")
    try:
        result=AssetLibrary(args.storage_root).import_pack(args.archive.read_bytes())
    except (OSError,LibraryError) as exc:
        print(f"Asset-pack import failed: {exc}",file=sys.stderr)
        return 1
    print(json.dumps({
        "imported":result["imported"],
        "production_candidates":result["production_candidates"],
        "reference_only":result["reference_only"],
        "fallback_candidates":result["fallback_candidates"],
        "status":"UNAPPROVED — review required",
    },indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
