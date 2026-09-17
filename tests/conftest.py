import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from blitz import db                                    # noqa: E402
from blitz.corpus.sample import load_sample             # noqa: E402


@pytest.fixture
def conn(tmp_path):
    connection = db.connect(tmp_path / "test.sqlite3")
    try:
        yield connection
    finally:
        connection.close()


@pytest.fixture
def seeded(conn):
    """An index holding both sample banks."""
    load_sample(conn, "business-management")
    load_sample(conn, "physics")
    return conn
