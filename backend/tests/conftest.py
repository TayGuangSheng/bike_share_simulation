from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import Base, SessionLocal, engine
from app.main import app
from app.seed import seed


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    seed()
    yield
    SessionLocal().close()


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)
