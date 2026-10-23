#!/usr/bin/env python3
"""Initialize a portable local DB from bundled source assets and metadata.

Usage: python -m scripts.bootstrap_factory
Safe to run multiple times. Does not connect to Facebook.
"""
import json
import os
from pathlib import Path

from services.database.repository import FactoryRepository

ROOT = Path(__file__).resolve().parents[1]
STORAGE = ROOT / "storage"


def bootstrap(db_path=None):
    path = Path(db_path or os.environ.get("SQLITE_DB_PATH", STORAGE / "factory.db"))
    repo = FactoryRepository(path)
    repo.seed_defaults(STORAGE / "browser_profiles")
    manifest = json.loads((STORAGE / "assets" / "asset_manifest.json").read_text(encoding="utf-8"))
    count = 0
    for item in manifest:
        species = item["species"]
        category = item["category"]
        base = STORAGE / "assets"
        target_folder = "objects" if category == "object" else "animals"
        png = base / target_folder / f"{species}.png"
        svg = base / "svg" / f"{species}.svg"
        outline = base / "outlines" / f"{species}_outline.png"
        if not png.is_file():
            raise FileNotFoundError(f"Missing bundled asset: {png}")
        repo.register_asset(
            asset_id=item["asset_id"],
            species=species,
            category=category,
            template_affinity=item["template_affinity"],
            png_path=str(png),
            svg_path=str(svg) if svg.is_file() else None,
            outline_png_path=str(outline) if outline.is_file() else None,
            width=int(item["width"]),
            height=int(item["height"]),
            sha256=item["sha256"],
            seed=int(item["seed"]),
            provenance=item.get("provenance", "bundled original artwork"),
            license_str=item.get("license", "License status to verify"),
            validation_dict=item.get("validation", {}),
        )
        count += 1
    print(f"Initialized {path} with {count} assets and demo Page placeholders (NOT logged in).")
    return repo


if __name__ == "__main__":
    bootstrap()
