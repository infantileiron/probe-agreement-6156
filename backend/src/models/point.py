from sqlalchemy import BigInteger,Boolean,Double,ForeignKey,Index,Integer,String,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from ..config.database import Base

PointKey=BigInteger().with_variant(Integer,"sqlite")


class _PointColumns:
 pair_id:Mapped[str]=mapped_column(String(80),nullable=False)
 range_label:Mapped[str]=mapped_column(String(10),nullable=False)
 x:Mapped[float]=mapped_column(Double,nullable=False)
 y:Mapped[float]=mapped_column(Double,nullable=False)
 mean:Mapped[float]=mapped_column(Double,nullable=False)
 difference:Mapped[float]=mapped_column(Double,nullable=False)
 fitted_y:Mapped[float]=mapped_column(Double,nullable=False)
 residual_y:Mapped[float]=mapped_column(Double,nullable=False)
 outside_loa:Mapped[bool]=mapped_column(Boolean,nullable=False,default=False)
 outside_tolerance:Mapped[bool]=mapped_column(Boolean,nullable=False,default=False)


# Per-pair detail lives in its own table so a million-pair run never has to be
# serialised into run.result. id is the keyset pagination cursor and preserves
# the source import order because chunks are inserted in order.
class RunPoint(_PointColumns,Base):
 __tablename__="run_points"
 id:Mapped[int]=mapped_column(PointKey,primary_key=True,autoincrement=True)
 run_id:Mapped[str]=mapped_column(String(36),ForeignKey("runs.id"),nullable=False)
 __table_args__=(
  UniqueConstraint("run_id","pair_id",name="uq_run_points_run_pair"),
  Index("ix_run_points_run_id_id","run_id","id"),
 )


# A report copies the completed run's points at approval time. The copy is the
# immutable archive: later run changes cannot alter an approved report, and the
# old snapshot rows remain exportable as-is.
class ReportPoint(_PointColumns,Base):
 __tablename__="report_points"
 id:Mapped[int]=mapped_column(PointKey,primary_key=True,autoincrement=True)
 report_id:Mapped[str]=mapped_column(String(36),ForeignKey("reports.id"),nullable=False)
 __table_args__=(
  UniqueConstraint("report_id","pair_id",name="uq_report_points_report_pair"),
  Index("ix_report_points_report_id_id","report_id","id"),
 )
