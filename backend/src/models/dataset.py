from sqlalchemy import String,Text,JSON,Integer
from sqlalchemy.orm import Mapped,mapped_column
from .common import RecordMixin
from ..config.database import Base
class PairedDataset(RecordMixin,Base):
 __tablename__="datasets"
 name:Mapped[str]=mapped_column(String(180),unique=True)
 x_unit:Mapped[str]=mapped_column(String(20))
 y_unit:Mapped[str]=mapped_column(String(20))
 # Legacy batches (imported before streaming existed) keep their <=5000-row
 # payload here and stay readable. New batches store rows in paired_readings and
 # leave this empty; pair_count is authoritative for both.
 pairs:Mapped[list]=mapped_column(JSON,default=list)
 description:Mapped[str]=mapped_column(Text,default="")
 pair_count:Mapped[int]=mapped_column(Integer,default=0)
 # Only "ready" batches are listed or usable. Streaming imports commit chunks
 # under "importing" so a bad row or duplicate never exposes a partial batch.
 status:Mapped[str]=mapped_column(String(20),default="ready",nullable=False)
