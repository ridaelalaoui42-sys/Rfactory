"""
Animal Puzzle Reels Factory — Core Services Package.
Includes StatMetaPathFinder so Python imports work deterministically on FUSE/VMAaS filesystems
where stat() is immediate even if readdir() is cached.
"""
from __future__ import annotations

import importlib.abc
import importlib.machinery
import importlib.util
import sys
from pathlib import Path


class _StatPathFinder(importlib.abc.MetaPathFinder):
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = Path(root_dir)

    def find_spec(self, fullname: str, path=None, target=None):
        rel = Path(*fullname.split("."))
        pkg_init = self.root_dir / rel / "__init__.py"
        if pkg_init.exists():
            return importlib.util.spec_from_file_location(
                fullname,
                str(pkg_init),
                submodule_search_locations=[str(pkg_init.parent)],
            )
        mod_py = (self.root_dir / rel).with_suffix(".py")
        if mod_py.exists():
            return importlib.util.spec_from_file_location(fullname, str(mod_py))
        return None


_REPO_ROOT = Path(__file__).resolve().parent.parent
if not any(isinstance(f, _StatPathFinder) for f in sys.meta_path):
    sys.meta_path.insert(0, _StatPathFinder(_REPO_ROOT))
