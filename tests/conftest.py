from pathlib import Path

import aiosqlite
import pytest

from app import try_make_db


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "test_sqlite.db"
    try_make_db(path)
    return path


@pytest.fixture
def upload_path(tmp_path: Path) -> Path:
    path = tmp_path / "test_upload"
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture
async def db(db_path: Path) -> aiosqlite.Connection:
    conn = await aiosqlite.connect(db_path)
    conn.row_factory = aiosqlite.Row
    yield conn
    await conn.close()
