from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from .settings import Settings


class StoragePathError(ValueError):
    pass


def _storage_root(settings: Settings | None = None) -> Path:
    settings = settings or Settings.from_env()
    return settings.storage_root.resolve()


def ensure_inside_storage(path: Path, settings: Settings | None = None) -> Path:
    root = _storage_root(settings)
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise StoragePathError(f"Path is outside STORAGE_ROOT: {path}") from exc
    return resolved


def block_attachment_dir(mine_id: int, site_id: int, block_id: int, settings: Settings | None = None) -> Path:
    root = _storage_root(settings)
    target = root / f"mine_{mine_id}" / f"site_{site_id}" / f"block_{block_id}" / "attachments"
    ensure_inside_storage(target, settings)
    target.mkdir(parents=True, exist_ok=True)
    return target


def unique_filename(original_filename: str) -> str:
    suffix = Path(original_filename).suffix.lower()
    safe_stem = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in Path(original_filename).stem)[:80]
    safe_stem = safe_stem or "attachment"
    return f"{safe_stem}_{uuid4().hex}{suffix}"


def copy_attachment(source_path: Path, mine_id: int, site_id: int, block_id: int, settings: Settings | None = None) -> Path:
    source = source_path.resolve(strict=True)
    target_dir = block_attachment_dir(mine_id, site_id, block_id, settings)
    target = target_dir / unique_filename(source.name)
    ensure_inside_storage(target, settings)
    shutil.copy2(source, target)
    return target.relative_to(_storage_root(settings))


def delete_physical_file(stored_relative_path: str, settings: Settings | None = None) -> None:
    root = _storage_root(settings)
    target = ensure_inside_storage(root / stored_relative_path, settings)
    if target.exists() and target.is_file():
        target.unlink()
