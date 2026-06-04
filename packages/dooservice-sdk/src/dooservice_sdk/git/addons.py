"""Scan a cloned addons directory for Odoo modules."""

from __future__ import annotations

from pathlib import Path

MANIFESTS = ("__manifest__.py", "__openerp__.py")
CONTAINER_DIR = "/mnt/extra-addons"


def scan(addons_path: Path) -> list[str]:
    """Walk the cloned repo and return container paths to feed `addons_path`."""
    if not addons_path.exists():
        return []

    parents: set[str] = set()
    for manifest in MANIFESTS:
        for manifest_file in addons_path.rglob(manifest):
            module_dir = manifest_file.parent
            parent = module_dir.parent
            if parent == addons_path:
                parents.add(CONTAINER_DIR)
            else:
                rel = parent.relative_to(addons_path)
                parents.add(f"{CONTAINER_DIR}/{rel}")
    return sorted(parents)


def is_module(path: Path) -> bool:
    return any((path / m).exists() for m in MANIFESTS)
