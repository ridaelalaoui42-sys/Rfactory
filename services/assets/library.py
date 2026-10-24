"""Curated, provenance-aware AI image library with explicit fallback semantics.

Imported images remain separate from existing procedural test assets.
Only original full-resolution images can become production candidates. Crops of
low-resolution catalog posters are reference-only, never upscaled and silently
used for final social video output.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import re
import secrets
import zipfile
from typing import Any

from PIL import Image, UnidentifiedImageError

VALID_CATEGORIES = {"animals", "characters", "vehicles", "fantasy", "objects", "backgrounds", "animal", "character", "vehicle", "object", "nature"}
VALID_TIERS = {"production_generated", "fallback", "reference_only", "user_uploaded"}
ID_RE = re.compile(r"^[a-f0-9]{32}$")
MIN_PRODUCTION_SIDE = 768
MAX_IMAGE_BYTES = 16 * 1024 * 1024
MAX_PIXELS = 24_000_000


class LibraryError(ValueError):
    pass


class AssetLibrary:
    def __init__(self, storage_root: Path):
        self.root = Path(storage_root) / "assets" / "library"
        self.images = self.root / "images"
        self.records = self.root / "records"
        self.images.mkdir(parents=True, exist_ok=True)
        self.records.mkdir(parents=True, exist_ok=True)

    def add_image(
        self, image_bytes: bytes, subject: str, category: str,
        tier: str, provenance: str, source_description: str,
        original_dimensions: tuple[int, int] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(image_bytes, bytes) or not 0 < len(image_bytes) <= MAX_IMAGE_BYTES:
            raise LibraryError("Image content is empty or exceeds 16 MB")
        if not 2 <= len(subject.strip()) <= 100 or not 4 <= len(provenance.strip()) <= 180:
            raise LibraryError("Subject and provenance are required")
        if category not in VALID_CATEGORIES or tier not in VALID_TIERS:
            raise LibraryError("Unknown asset category or tier")
        if len(source_description) > 500:
            raise LibraryError("Source description is too long")
        try:
            with Image.open(io.BytesIO(image_bytes)) as source:
                source.load()
                width, height = source.size
                if width * height > MAX_PIXELS or width < 24 or height < 24:
                    raise LibraryError("Invalid image dimensions")
                if source.format not in {"PNG", "JPEG", "WEBP"}:
                    raise LibraryError("Use genuine PNG, JPEG or WebP source image")
                converted = source.convert("RGBA")
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise LibraryError("The supplied image is not a valid media file") from exc
        orig_w, orig_h = original_dimensions or (width, height)
        # A thumbnail later stretched to 1024 must remain labeled reference
        # only; approval cannot override the ORIGINAL effective resolution.
        meets_resolution = min(width, height, orig_w, orig_h) >= MIN_PRODUCTION_SIDE
        available_for_production = bool(meets_resolution and tier != "reference_only")
        if not meets_resolution:
            tier = "reference_only"

        key = secrets.token_hex(16)
        content_sha256 = hashlib.sha256(image_bytes).hexdigest()
        output = self.images / f"{key}.png"
        converted.save(output, optimize=True)
        metadata = {
            "id": key,
            "subject": subject.strip(),
            "category": category,
            "tier": tier,
            "provenance": provenance,
            "source_description": source_description,
            "original_dimensions": [orig_w, orig_h],
            "width": width,
            "height": height,
            "sha256": content_sha256,
            "pixel_sha256": hashlib.sha256(converted.tobytes()).hexdigest(),
            "approved": False,
            "production_eligible": available_for_production,
            "review_status": "AWAITING_REVIEW" if available_for_production else "REFERENCE_ONLY",
            "is_fallback": tier == "fallback",
            "media_url": f"/api/v1/library/media/{key}",
        }
        (self.records / f"{key}.json").write_text(
            json.dumps(metadata, sort_keys=True, indent=2), encoding="utf-8"
        )
        return metadata

    def import_pack(self, zip_bytes: bytes, max_items: int = 200) -> dict[str, Any]:
        """Import a Rfactory asset pack with size/hash/path validation.

        Verify *every* member before writing any library records, so malformed
        archives cannot leave misleading partially imported asset catalogs.
        """
        if not 0 < len(zip_bytes) <= 60 * 1024 * 1024:
            raise LibraryError("Pack ZIP must be between 1 byte and 60 MB")
        import_zip = io.BytesIO(zip_bytes)
        try:
            with zipfile.ZipFile(import_zip) as archive:
                manifest_info = archive.getinfo("manifest.json")
                if manifest_info.file_size > 2 * 1024 * 1024:
                    raise LibraryError("Asset manifest is too large")
                manifest = json.loads(archive.read("manifest.json"))
                records = manifest.get("assets", [])
                if not isinstance(records, list) or not 1 <= len(records) <= max_items:
                    raise LibraryError("Asset-pack entry count invalid")
                files_to_import = []
                observed = set()
                size_total = 0
                for meta in records:
                    relative = meta.get("file")
                    if not isinstance(relative, str) or relative.startswith("/") or "\\" in relative:
                        raise LibraryError("Unsafe pack member name")
                    fragments = Path(relative).parts
                    if not fragments or ".." in fragments or relative in observed:
                        raise LibraryError("Duplicate or unsafe asset path")
                    observed.add(relative)
                    info = archive.getinfo(relative)
                    if info.file_size > MAX_IMAGE_BYTES:
                        raise LibraryError("Oversized image in asset pack")
                    size_total += info.file_size
                    if size_total > 200 * 1024 * 1024:
                        raise LibraryError("Uncompressed pack exceeds size limit")
                    payload = archive.read(relative)
                    if hashlib.sha256(payload).hexdigest() != meta.get("sha256"):
                        raise LibraryError(f"Pack media checksum mismatch: {relative}")
                    original_size = meta.get("source_dimensions")
                    if not (isinstance(original_size, list) and len(original_size) == 2
                            and all(isinstance(v, int) and v > 0 for v in original_size)):
                        raise LibraryError(f"Missing original image dimensions: {relative}")
                    files_to_import.append((meta, payload, tuple(original_size)))
        except (zipfile.BadZipFile, KeyError, json.JSONDecodeError) as exc:
            raise LibraryError("Pack has an invalid archive or manifest") from exc

        imported = []
        for meta, payload, dimensions in files_to_import:
            imported.append(self.add_image(
                payload,
                subject=str(meta["subject"]),
                category=str(meta["category"]),
                tier=str(meta["tier"]),
                provenance=str(meta["provenance"]),
                source_description=str(meta.get("source_description") or "Imported asset pack"),
                original_dimensions=dimensions,
            ))
        return {
            "imported": len(imported),
            "production_candidates": sum(item["production_eligible"] for item in imported),
            "reference_only": sum(not item["production_eligible"] for item in imported),
            "fallback_candidates": sum(item["is_fallback"] for item in imported),
            "assets": imported,
        }

    def get(self, asset_id: str) -> dict[str, Any]:
        if not ID_RE.fullmatch(asset_id):
            raise LibraryError("Invalid asset identifier")
        path = self.records / f"{asset_id}.json"
        if not path.is_file():
            raise FileNotFoundError(asset_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def path(self, asset_id: str) -> Path:
        self.get(asset_id)
        path = self.images / f"{asset_id}.png"
        if not path.is_file():
            raise FileNotFoundError(asset_id)
        return path

    def approve(self, asset_id: str) -> dict[str, Any]:
        item = self.get(asset_id)
        if not item["production_eligible"]:
            raise LibraryError(
                "Low-resolution catalog reference cannot be approved for final video. Regenerate source artwork at 768px+."
            )
        item["approved"] = True
        item["review_status"] = "APPROVED"
        (self.records / f"{asset_id}.json").write_text(
            json.dumps(item, sort_keys=True, indent=2), encoding="utf-8"
        )
        return item

    def list_assets(
        self, category: str | None = None, production_only: bool = False,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if category is not None and category not in VALID_CATEGORIES:
            raise LibraryError("Invalid category")
        if not 1 <= limit <= 500:
            raise LibraryError("Asset limit out of bounds")
        result = []
        for path in sorted(self.records.glob("*.json")):
            try:
                item = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if category and item.get("category") != category:
                continue
            if production_only and not item.get("production_eligible", False):
                continue
            result.append(item)
            if len(result) >= limit:
                break
        return result

    def select(
        self, category: str, subject: str | None = None,
        allow_fallback: bool = False, seed: int = 0,
    ) -> dict[str, Any]:
        """Opt-in fallback; NEVER pretend a fallback was generated by Gemini."""
        if category not in VALID_CATEGORIES:
            raise LibraryError("Invalid category")
        items = [
            x for x in self.list_assets(category=category, limit=500)
            if x["approved"] and x["production_eligible"]
        ]
        if subject:
            subject_lower = subject.casefold()
            items = [x for x in items if subject_lower in x["subject"].casefold()]
        primary = [x for x in items if not x["is_fallback"]]
        pool = primary or ([x for x in items if x["is_fallback"]] if allow_fallback else [])
        if not pool:
            raise LibraryError("No approved production artwork for this request. Generate new AI artwork or explicitly allow an approved fallback.")
        pool.sort(key=lambda item: item["id"])
        selected = dict(pool[seed % len(pool)])
        selected["selected_as_fallback"] = bool(selected["is_fallback"])
        selected["generation_attempted"] = False
        selected["selection_note"] = (
            "EXPLICIT FALLBACK: previously generated/curated artwork was reused. "
            "No current Gemini image generation occurred."
            if selected["selected_as_fallback"]
            else "Existing approved original artwork was reused; no current generation occurred."
        )
        return selected
