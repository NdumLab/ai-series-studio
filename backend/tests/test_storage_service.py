"""Unit tests for generated asset storage foundation."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from storage_service import (  # noqa: E402
    LocalStorageBackend,
    asset_metadata,
    config_snapshot,
    make_storage_key,
    storage_backend,
    storage_config,
    validate_storage_key,
)


def test_local_storage_config_loads(tmp_path):
    cfg = storage_config({
        "ASSET_STORAGE_BACKEND": "local",
        "ASSET_LOCAL_DIR": str(tmp_path),
    })

    assert cfg.backend == "local"
    assert cfg.local_dir == tmp_path
    assert cfg.public_base_url == "/assets"
    assert config_snapshot(cfg)["s3_configured"] is False


def test_generated_storage_key_is_safe():
    key = make_storage_key(
        user_id="user/../bad",
        project_id="proj 1",
        asset_type="scene_image",
        asset_id="asset:1",
        mime_type="image/png",
    )

    assert ".." not in key
    assert key.endswith(".png")
    assert validate_storage_key(key) == key


def test_path_traversal_is_rejected():
    with pytest.raises(ValueError):
        validate_storage_key("../outside.png")
    with pytest.raises(ValueError):
        validate_storage_key("/absolute/path.png")


def test_local_save_asset_bytes_and_exists(tmp_path):
    cfg = storage_config({
        "ASSET_STORAGE_BACKEND": "local",
        "ASSET_LOCAL_DIR": str(tmp_path),
    })
    backend = LocalStorageBackend(cfg)
    key = "user/project/scene_image/test.png"

    saved = backend.save_bytes(key, b"image-bytes")

    assert saved["size_bytes"] == 11
    assert saved["url"] == "/assets/user/project/scene_image/test.png"
    assert backend.exists(key) is True
    assert (tmp_path / key).read_bytes() == b"image-bytes"
    assert backend.delete(key) is True
    assert backend.exists(key) is False


def test_external_url_asset_metadata_no_network_call(tmp_path):
    cfg = storage_config({
        "ASSET_STORAGE_BACKEND": "local",
        "ASSET_LOCAL_DIR": str(tmp_path),
    })
    backend = storage_backend(cfg)
    key = make_storage_key(
        user_id="user-1",
        project_id="project-1",
        asset_type="scene_image",
        asset_id="asset-1",
        source_name="https://example.com/mock.png",
    )
    stored = backend.save_external_url(key, "https://example.com/mock.png")
    doc = asset_metadata(
        asset_id="asset-1",
        user_id="user-1",
        project_id="project-1",
        scene_id="scene-1",
        asset_type="scene_image",
        storage_backend_name=cfg.backend,
        storage_key=stored["storage_key"],
        url=stored["url"],
        external_url=stored["external_url"],
        mime_type="image/png",
        size_bytes=stored["size_bytes"],
        provider_name="mock-image",
        provider_job_id=None,
        created_at="2026-01-01T00:00:00+00:00",
    )

    assert doc["url"] == "https://example.com/mock.png"
    assert doc["external_url"] == "https://example.com/mock.png"
    assert doc["size_bytes"] == 0
    assert doc["asset_type"] == "scene_image"
    assert not Path(tmp_path / key).exists()


def test_s3_backend_stub_requires_no_aws_credentials(monkeypatch):
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    cfg = storage_config({"ASSET_STORAGE_BACKEND": "s3", "ASSET_S3_BUCKET": ""})
    backend = storage_backend(cfg)

    assert backend.config.backend == "s3"
    with pytest.raises(NotImplementedError):
        backend.save_bytes("user/project/scene_image/test.png", b"x")
