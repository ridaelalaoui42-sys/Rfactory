#!/usr/bin/env python3
"""Inspect the Rfactory release ZIP without extracting or executing untrusted content."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path, PurePosixPath
import sys
import zipfile

EXPECTED_SHA256 = "c025e8c27904ed0205085377022339d5d9915ee08752a148745c116b9850b940"
EXPECTED_BYTES = 30362257

def main():
    archive = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/rfactory-release/Apf.zip")
    report = Path("docs/RELEASE_ARCHIVE_INVENTORY.md")
    report.parent.mkdir(parents=True, exist_ok=True)
    data_hash = hashlib.sha256()
    with archive.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            data_hash.update(chunk)
    sha = data_hash.hexdigest()
    if sha != EXPECTED_SHA256 or archive.stat().st_size != EXPECTED_BYTES:
        raise SystemExit("Release digest/size mismatch; refusing to inspect unknown archive.")
    with zipfile.ZipFile(archive) as zf:
        files = [i for i in zf.infolist() if not i.is_dir()]
        if zf.testzip():
            raise SystemExit("ZIP CRC verification failed.")
    ext = Counter(Path(i.filename).suffix.lower() or "(none)" for i in files)
    top = Counter(i.filename.replace("\\", "/").split("/")[0] for i in files)
    unsafe = [i.filename for i in files if i.filename.startswith("/") or ".." in PurePosixPath(i.filename).parts or "\\" in i.filename]
    suspicious = [i.filename for i in files if any(
        x in i.filename.lower() for x in (".env", "credential", "secret", "private_key", ".pem", ".p12", ".pfx", "id_rsa", ".git/", "node_modules/", ".venv/")
    )]
    sample = sorted(files, key=lambda f: f.filename.lower())
    lines = [
        "# Rfactory Release ZIP Inventory",
        "",
        "Read-only analysis of the `Repo` release asset. Archive contents have **not** been extracted, executed or committed.",
        "",
        f"- Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"- Asset: [Apf.zip](https://github.com/ridaelalaoui42-sys/Rfactory/releases/download/Repo/Apf.zip)",
        f"- ZIP size: {archive.stat().st_size:,} bytes",
        f"- Verified SHA-256: `{sha}`",
        f"- File entries: {len(files):,}",
        f"- Declared uncompressed bytes: {sum(i.file_size for i in files):,}",
        f"- Suspicious paths needing review: {len(suspicious)}",
        f"- Unsafe traversal paths: {len(unsafe)}",
        "",
        "## Top-level folders",
        "",
    ]
    lines += [f"- `{name}`: {cnt} files" for name, cnt in top.most_common(30)]
    lines += ["", "## File extensions", ""]
    lines += [f"- `{name}`: {cnt}" for name, cnt in ext.most_common(40)]
    lines += ["", "## Source/build clues", ""]
    clues = ["package.json","pyproject.toml","requirements.txt","Dockerfile","docker-compose.yml","compose.yml","next.config.js","next.config.ts","remotion.config.ts","vite.config.ts","README.md"]
    for clue in clues:
        matched = [i.filename for i in files if PurePosixPath(i.filename).name == clue]
        if matched:
            lines += [f"- `{clue}`: " + ", ".join("`"+f+"`" for f in matched[:10])]
    lines += ["", "## Paths needing manual review", ""]
    lines += ["- " + "`" + v.replace("`", "") + "`" for v in suspicious[:100]] or ["- None detected by filename heuristics."]
    lines += ["", "## Archive file listing (first 400 alphabetically)", "", "| Path | Bytes |", "|---|---:|"]
    lines += ["| `"+i.filename.replace("|","/").replace("`","")+"` | "+str(i.file_size)+" |" for i in sample[:400]]
    if len(sample) > 400:
        lines += ["", f"_Omitted {len(sample)-400:,} additional entries. All counts reflect the full archive._"]
    lines += ["", "## Security decision", "", "Inventory only. Before extracting into a public GitHub branch, filter secrets, caches, dependencies, and generated/binary content. Never execute release-provided code until reviewed.", ""]
    report.write_text("\n".join(lines), encoding="utf-8")
    print(f"Verified archive SHA-256 {sha}. Inventory: {len(files)} files, {sum(i.file_size for i in files)} uncompressed bytes. Report: {report}")

if __name__ == "__main__":
    main()
