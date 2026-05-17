"""Generated asset storage foundation.

Local storage is the only implemented backend. S3/R2 classes are placeholders
until production credentials and storage policy are wired. Raw binary data is
never stored in MongoDB; callers persist metadata records separately.
"""
from __future__ import annotations

import mimetypes
import os
import shutil
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Optional
from urllib.parse import urlparse


ASSET_TYPES = {
    "character_image",
    "scene_image",
    "video_segment",
    "voice_audio",
    "music_audio",
    "export_video",
}


@dataclass(frozen=True)
class AssetStorageConfig:
    backend: str
    local_dir: Path
    public_base_url: str
    s3_bucket: str
    s3_region: str
    s3_prefix: str
    signed_url_expire_seconds: int


def storage_config(env: Optional[dict] = None, root_dir: Optional[Path] = None) -> AssetStorageConfig:
    source = env if env is not None else os.environ
    backend = (source.get("ASSET_STORAGE_BACKEND") or "local").strip().lower() or "local"
    base = root_dir or Path(__file__).parent
    local_raw = (source.get("ASSET_LOCAL_DIR") or "./generated_assets").strip()
    local_dir = Path(local_raw)
    if not local_dir.is_absolute():
        local_dir = (base / local_dir).resolve()
    try:
        expire = int(source.get("ASSET_SIGNED_URL_EXPIRE_SECONDS") or "3600")
    except (TypeError, ValueError):
        expire = 3600
    return AssetStorageConfig(
        backend=backend,
        local_dir=local_dir,
        public_base_url=(source.get("ASSET_PUBLIC_BASE_URL") or "http://localhost:8000/assets").strip().rstrip("/"),
        s3_bucket=(source.get("ASSET_S3_BUCKET") or "").strip(),
        s3_region=(source.get("ASSET_S3_REGION") or "us-east-1").strip(),
        s3_prefix=(source.get("ASSET_S3_PREFIX") or "ai-series-studio").strip().strip("/"),
        signed_url_expire_seconds=max(60, expire),
    )


def _safe_part(value: Optional[str], fallback: str) -> str:
    raw = (value or fallback).strip()
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in raw)
    return safe.strip("-") or fallback


def _extension(mime_type: Optional[str], source_name: Optional[str] = None) -> str:
    if source_name:
        suffix = Path(urlparse(source_name).path).suffix.lower()
        if suffix and len(suffix) <= 8:
            return suffix
    guessed = mimetypes.guess_extension(mime_type or "application/octet-stream")
    return guessed or ".bin"


def make_storage_key(
    *,
    user_id: str,
    project_id: str,
    asset_type: str,
    asset_id: Optional[str] = None,
    mime_type: Optional[str] = None,
    source_name: Optional[str] = None,
) -> str:
    if asset_type not in ASSET_TYPES:
        raise ValueError(f"Unknown asset_type: {asset_type}")
    aid = _safe_part(asset_id or str(uuid.uuid4()), "asset")
    parts = [
        _safe_part(user_id, "user"),
        _safe_part(project_id, "project"),
        _safe_part(asset_type, "asset"),
        f"{aid}{_extension(mime_type, source_name)}",
    ]
    return str(PurePosixPath(*parts))


def validate_storage_key(storage_key: str) -> str:
    if not storage_key or storage_key.startswith("/"):
        raise ValueError("Invalid storage key")
    pure = PurePosixPath(storage_key)
    if any(part in {"", ".", ".."} for part in pure.parts):
        raise ValueError("Invalid storage key")
    return str(pure)


class LocalStorageBackend:
    def __init__(self, config: AssetStorageConfig) -> None:
        self.config = config

    def _path(self, storage_key: str) -> Path:
        safe_key = validate_storage_key(storage_key)
        target = (self.config.local_dir / safe_key).resolve()
        root = self.config.local_dir.resolve()
        if root != target and root not in target.parents:
            raise ValueError("Invalid storage key")
        return target

    def save_bytes(self, storage_key: str, data: bytes) -> dict:
        path = self._path(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return {"storage_key": validate_storage_key(storage_key), "size_bytes": len(data), "url": self.url_for(storage_key)}

    def save_external_url(self, storage_key: str, external_url: str) -> dict:
        # External mock/provider URLs are recorded as metadata only. No network
        # fetch happens in tests or mock mode.
        return {
            "storage_key": validate_storage_key(storage_key),
            "size_bytes": 0,
            "url": external_url,
            "external_url": external_url,
        }

    def url_for(self, storage_key: str) -> str:
        return f"{self.config.public_base_url}/{validate_storage_key(storage_key)}"

    def exists(self, storage_key: str) -> bool:
        return self._path(storage_key).exists()

    def delete(self, storage_key: str) -> bool:
        path = self._path(storage_key)
        if not path.exists():
            return False
        path.unlink()
        return True


class DisabledStorageBackend:
    def save_bytes(self, storage_key: str, data: bytes) -> dict:
        return {"storage_key": validate_storage_key(storage_key), "size_bytes": 0, "url": ""}

    def save_external_url(self, storage_key: str, external_url: str) -> dict:
        return {"storage_key": validate_storage_key(storage_key), "size_bytes": 0, "url": external_url, "external_url": external_url}

    def url_for(self, storage_key: str) -> str:
        return ""

    def exists(self, storage_key: str) -> bool:
        return False

    def delete(self, storage_key: str) -> bool:
        return False


class S3StorageBackend:
    """Future S3/R2-compatible backend placeholder."""
    def __init__(self, config: AssetStorageConfig) -> None:
        self.config = config

    def save_bytes(self, storage_key: str, data: bytes) -> dict:  # pragma: no cover - future stub
        raise NotImplementedError("S3/R2 asset upload is not wired yet")


class R2StorageBackend(S3StorageBackend):
    """Future Cloudflare R2 backend placeholder."""


def storage_backend(config: Optional[AssetStorageConfig] = None):
    cfg = config or storage_config()
    if cfg.backend == "local":
        return LocalStorageBackend(cfg)
    if cfg.backend == "disabled":
        return DisabledStorageBackend()
    if cfg.backend in {"s3", "r2"}:
        return S3StorageBackend(cfg) if cfg.backend == "s3" else R2StorageBackend(cfg)
    return DisabledStorageBackend()


def asset_metadata(
    *,
    asset_id: str,
    user_id: str,
    project_id: str,
    asset_type: str,
    storage_backend_name: str,
    storage_key: str,
    url: str,
    mime_type: str,
    size_bytes: int,
    provider_name: str,
    provider_job_id: Optional[str],
    created_at: str,
    scene_id: Optional[str] = None,
    segment_id: Optional[str] = None,
    external_url: Optional[str] = None,
) -> dict:
    if asset_type not in ASSET_TYPES:
        raise ValueError(f"Unknown asset_type: {asset_type}")
    doc = {
        "id": asset_id,
        "user_id": user_id,
        "project_id": project_id,
        "scene_id": scene_id,
        "segment_id": segment_id,
        "asset_type": asset_type,
        "storage_backend": storage_backend_name,
        "storage_key": validate_storage_key(storage_key),
        "url": url,
        "mime_type": mime_type,
        "size_bytes": int(size_bytes or 0),
        "provider_name": provider_name,
        "provider_job_id": provider_job_id,
        "created_at": created_at,
    }
    if external_url:
        doc["external_url"] = external_url
    return doc


def config_snapshot(config: Optional[AssetStorageConfig] = None) -> dict:
    cfg = config or storage_config()
    data = asdict(cfg)
    data["local_dir"] = str(cfg.local_dir)
    data["s3_configured"] = bool(cfg.s3_bucket)
    return data


def remove_local_tree_for_project(config: AssetStorageConfig, user_id: str, project_id: str) -> None:
    root = (config.local_dir / _safe_part(user_id, "user") / _safe_part(project_id, "project")).resolve()
    base = config.local_dir.resolve()
    if base != root and base in root.parents and root.exists():
        shutil.rmtree(root)
