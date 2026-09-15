import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("MOCK_MODE", "true")
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{ROOT}/test_workflowos.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("WORKFLOWOS_FAST_RETRY", "1")

import pytest_asyncio  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def _init_test_db():
    from backend.models.db import init_db

    await init_db()
    yield
