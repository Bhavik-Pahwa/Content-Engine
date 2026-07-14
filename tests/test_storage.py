from __future__ import annotations

from pathlib import Path

from content_engine.config import load_settings
from content_engine.storage import initialize_storage


def test_initialize_storage_creates_required_directories(tmp_path: Path) -> None:
    settings = load_settings(env={}, base_dir=tmp_path)

    paths = initialize_storage(settings.storage, settings.logging)

    for directory in paths.all_directories():
        assert directory.exists()
        assert directory.is_dir()

