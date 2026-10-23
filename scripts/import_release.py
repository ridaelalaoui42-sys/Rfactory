#!/usr/bin/env python3
"""Safely import reviewed source and static assets from the verified release ZIP.

Only project source/static assets are imported. No archive code is executed.
Runtime database files, exports, credentials, generated binaries and common
dependency/build folders are deliberately excluded from the public repository.
"""
from collections import Counter
from datetime import datetime, timezone
import hashlib
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import zipfile

SHA256 = "c025e8c27904ed0205085377022339d5d9915ee08752a148745c116b9850b940"
EXPECTED_BYTES = 30362257
ARCHIVE_PREFIX = "animal-puzzle-reels-factory/"
MAX_FILE = 15 * 1024 * 1024
MAX_TOTAL = 150 * 1024 * 1024
ALLOW_EXTENSIONS = {".py",".ts",".tsx",".js",".jsx",".md",".json",".yml",".yaml",
                    ".sql",".html",".css",".txt",".svg",".png",".jpg",".jpeg",
                    ".webp",".toml",".example",".sh",".dockerignore",".gitignore"}
ALLOW_EXACT = {"Dockerfile","Makefile",".gitignore",".dockerignore"}
BLOCKED_PARTS = {".git","node_modules",".next",".venv","venv","__pycache__",
                 ".pytest_cache","coverage","dist","build",".cache","playwright-report",
                 "test-results",".idea",".vscode"}
BLOCKED_SUFFIXES = {".db",".sqlite",".sqlite3",".pem",".key",".p12",".pfx",".crt",".pyc"}
SENSITIVE_PATTERNS = [
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"ghp_[A-Za-z0-9_]{25,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{25,}"),
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{32,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"EAAB[A-Za-z0-9]{40,}"),
]

def main():
    path = Path(sys.argv[1] if len(sys.argv)>1 else "/tmp/rfactory-release/Apf.zip")
    if path.stat().st_size != EXPECTED_BYTES:
        raise SystemExit("Unexpected archive size")
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != SHA256:
        raise SystemExit("Release checksum mismatch")
    included, excluded, included_bytes = [], [], 0
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if sum(i.file_size for i in entries) > MAX_TOTAL:
            raise SystemExit("Uncompressed archive exceeds safe import limit")
        for entry in entries:
            name = entry.filename
            if entry.is_dir():
                continue
            if not name.startswith(ARCHIVE_PREFIX):
                excluded.append((name,"outside expected project root"))
                continue
            relative = name[len(ARCHIVE_PREFIX):]
            parts = PurePosixPath(relative).parts
            if not relative or relative.startswith("/") or "\\" in relative or "." in parts or ".." in parts:
                raise SystemExit("Archive includes unsafe path: "+name)
            if (entry.external_attr >> 16) & stat.S_IFMT(0o170000) == stat.S_IFLNK:
                excluded.append((relative,"symlink"))
                continue
            ext = Path(relative).suffix.lower()
            lower = relative.lower()
            if any(p.lower() in BLOCKED_PARTS for p in parts):
                excluded.append((relative,"build/dependency/cache"))
                continue
            if (lower.startswith("storage/exports/") or lower.startswith("storage/runtime/") or
                lower.startswith("storage/sessions/") or lower.startswith("storage/logs/") or
                ext in BLOCKED_SUFFIXES or (Path(relative).name.startswith(".env") and Path(relative).name != ".env.example")):
                excluded.append((relative,"generated/runtime/credential material"))
                continue
            if ext not in ALLOW_EXTENSIONS and Path(relative).name not in ALLOW_EXACT:
                excluded.append((relative,"unsupported extension"))
                continue
            if entry.file_size > MAX_FILE:
                excluded.append((relative,"oversized file"))
                continue
            data = archive.read(entry)
            if ext not in {".png",".jpg",".jpeg",".webp"}:
                if any(regex.search(data.decode("utf-8","ignore")) for regex in SENSITIVE_PATTERNS):
                    excluded.append((relative,"possible credential/token"))
                    continue
            target = Path(relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            included.append(relative)
            included_bytes += len(data)
    report = Path("docs/RELEASE_IMPORT_REPORT.md")
    report.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Rfactory Release Import Report", "",
        "The verified release archive was imported without executing code. No changes were made to `main`.",
        "",
        f"- Archive: [Apf.zip](https://github.com/ridaelalaoui42-sys/Rfactory/releases/download/Repo/Apf.zip)",
        f"- Verified digest: `{SHA256}`",
        f"- Imported: **{len(included)}** source/static files ({included_bytes:,} bytes)",
        f"- Skipped: **{len(excluded)}** files",
        f"- Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "", "## Files deliberately excluded", "",
        "| Archive-relative path | Reason |", "|---|---|"
    ]
    for name,reason in excluded:
        lines.append(f"| `{name.replace('|','/')}` | {reason} |")
    lines += ["","## Next steps","",
        "Review imported code for correctness, secret management, injection risks and publication safeguards.",
        "Run tests in an isolated CI job with dependency pinning before considering deployment.",
        "The original ZIP remains available in Releases for recovery; no original release files were deleted.",
        ""]
    report.write_text("\n".join(lines), encoding="utf-8")
    print(f"Imported {len(included)} files ({included_bytes:,} bytes); skipped {len(excluded)}.")
    print("Excluded:",excluded)

if __name__ == "__main__":
    main()
