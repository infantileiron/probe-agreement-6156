from sqlalchemy import String,Text,JSON,ForeignKey,Double,Integer
from sqlalchemy.orm import Mapped,mapped_column
from .common import RecordMixin
from ..config.database import Base
class CalibrationRun(RecordMixin,Base):
 __tablename__="runs"
 study_id:Mapped[str]=mapped_column(ForeignKey("studies.id"))
 status:Mapped[str]=mapped_column(String(20),default="queued")
 # Aggregates only. Per-pair detail lives in run_points so a million-pair run
 # never serialises its whole hair into one JSON document.
 result:Mapped[dict]=mapped_column(JSON,default=dict)
 # Bounded, evenly strided subset used by charts. Charts always quote its size.
 sample:Mapped[list]=mapped_column(JSON,default=list)
 progress:Mapped[int]=mapped_column(Integer,default=0)
 phase:Mapped[str]=mapped_column(String(20),default="")
 error:Mapped[str]=mapped_column(Text,default="")
