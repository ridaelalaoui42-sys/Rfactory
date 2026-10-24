"""Safely install the separately delivered Rfactory social asset ZIP."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import zipfile

def install(archive: Path, dest: Path) -> dict:
    if not archive.is_file():
        raise FileNotFoundError(archive)
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        members = z.infolist()
        if len(members) > 1000:
            raise ValueError("Too many ZIP entries")
        for m in members:
            name = Path(m.filename)
            if name.is_absolute() or '..' in name.parts or m.file_size > 20 * 1024 * 1024:
                raise ValueError(f"Unsafe ZIP entry: {m.filename}")
        entries = [m for m in members if not m.is_dir()]
        if sum(m.file_size for m in entries) > 400 * 1024 * 1024:
            raise ValueError("Oversized asset archive")
        for m in entries:
            pieces = Path(m.filename).parts
            if 'rfactory_social_asset_library' in pieces:
                n = pieces.index('rfactory_social_asset_library')
                pieces = pieces[n+1:]
            if not pieces:
                continue
            if pieces[0] not in {'assets', 'backgrounds', 'source_sheets', 'asset-catalog.json', 'README.md', 'index.html', 'sample_compositions'}:
                continue
            path = dest.joinpath(*pieces)
            path.parent.mkdir(parents=True, exist_ok=True)
            with z.open(m) as src, path.open('wb') as dst:
                for chunk in iter(lambda: src.read(1024 * 1024), b''):
                    dst.write(chunk)
    catalog = json.loads((dest / 'asset-catalog.json').read_text())
    return {'total':len(catalog['entries']), 'dest':str(dest)}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('archive', type=Path)
    parser.add_argument('--dest',type=Path,default=Path('public/rfactory-social'))
    args=parser.parse_args()
    print(json.dumps(install(args.archive,args.dest),indent=2))
