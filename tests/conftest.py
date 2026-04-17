"""Shared pytest fixtures for the kxt test suite."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).parent / "fakes"


@pytest.fixture
def krx_fixture_csv() -> bytes:
    return (FIXTURE_DIR / "krx_master_fixture.csv").read_bytes()


@pytest.fixture
def tmp_cache_dir(tmp_path: Path) -> Path:
    d = tmp_path / "cache"
    d.mkdir()
    return d
