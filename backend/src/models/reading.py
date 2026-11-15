from sqlalchemy import BigInteger,Double,ForeignKey,Index,Integer,String,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from ..config.database import Base

# Auto-increment key is intentionally the pagination cursor: rows for one import are
# inserted in source order, so keyset pagination by id is stable and gap-free.
ReadingKey=BigInteger().with_variant(Integer,"sqlite")

class PairedReading(Base):
 __tablename__="paired_readings"
 id:Mapped[int]=mapped_column(ReadingKey,primary_key=True,autoincrement=True)
 dataset_id:Mapped[str]=mapped_column(String(36),ForeignKey("datasets.id"),nullable=False)
 pair_id:Mapped[str]=mapped_column(String(80),nullable=False)
 range_label:Mapped[str]=mapped_column(String(10),nullable=False)
 x:Mapped[float]=mapped_column(Double,nullable=False)
 y:Mapped[float]=mapped_column(Double,nullable=False)
 __table_args__=(
  UniqueConstraint("dataset_id","pair_id",name="uq_paired_readings_dataset_pair"),
  Index("ix_paired_readings_dataset_id_id","dataset_id","id"),
 )
