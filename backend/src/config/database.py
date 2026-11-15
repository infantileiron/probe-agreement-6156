from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase,sessionmaker
from .settings import DATABASE_URL
class Base(DeclarativeBase): pass

# MySQL is the deployment target. SQLite is supported for local runs and the
# bounded-memory test harness; it needs check_same_thread disabled because
# FastAPI serves dependencies and endpoints from a thread pool.
if DATABASE_URL.startswith("sqlite"):
 engine=create_engine(DATABASE_URL,connect_args={"check_same_thread":False},pool_pre_ping=True)
else:
 engine=create_engine(DATABASE_URL,pool_pre_ping=True)
Session=sessionmaker(bind=engine,expire_on_commit=False)
def get_db():
 with Session() as db: yield db
def initialize():
 from .. import models
 Base.metadata.create_all(engine)
