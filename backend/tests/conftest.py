import os,sys,tempfile
from pathlib import Path
import pytest

BACKEND=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BACKEND))
# Must be set before any src import so the engine binds to a scratch database.
_DB_DIR=tempfile.mkdtemp(prefix="probe-tests-")
os.environ["DATABASE_URL"]=f"sqlite:///{_DB_DIR}/tests.db"
os.environ["SEED_DEMO"]="false"

from src.config.database import Base,Session,engine  # noqa: E402
from src import models  # noqa: F401,E402


@pytest.fixture()
def db():
 """Empty schema for every test; the engine itself is process-wide."""
 Base.metadata.drop_all(engine)
 Base.metadata.create_all(engine)
 with Session() as session:yield session
