import io
from sqlalchemy import func,select

from src.models.dataset import PairedDataset
from src.models.reading import PairedReading
from src.models.point import RunPoint
from src.services import dataset_service,run_service
from src.services.stream_store import count_points


def _csv(n,dup_at=None,dup_of=None,bad_at=None,trailing=False):
 lines=["pair_id,range_label,x,y"]
 for i in range(n):
  pid=f"P{i:05d}" if not (dup_at==i and dup_of is not None) else f"P{dup_of:05d}"
  x=20+i*.01;y=x+.25+((i%97)-48)*.002
  y_text="not-a-number" if bad_at==i else f"{y:.6f}"
  lines.append(f"{pid},{['low','middle','high'][min(i*3//max(n,1),2)]},{x:.6f},{y_text}")
 if trailing:lines.append("")
 return ("\n".join(lines)+"\n").encode()


def _counts(db):
 return (db.scalar(select(func.count()).select_from(PairedReading)),
         db.scalar(select(func.count()).select_from(PairedDataset)))


def test_stream_import_stores_all_rows_in_paired_readings(db):
 ds=dataset_service.create_streaming(db,"b1","kPa","kPa","desc",io.BytesIO(_csv(12345)),batch_rows=5000)
 assert ds.pair_count==12345 and ds.status=="ready" and ds.pairs==[]
 assert _counts(db)==(12345,1)


def test_last_row_bad_rows_are_invisible_and_retryable(db):
 with __import__("pytest").raises(Exception) as exc:
  dataset_service.create_streaming(db,"b2","kPa","kPa","",io.BytesIO(_csv(20,bad_at=19)),batch_rows=5)
 assert "第21行" in str(getattr(exc.value,"detail",exc.value))
 assert _counts(db)==(0,0)
 ds=dataset_service.create_streaming(db,"b2","kPa","kPa","",io.BytesIO(_csv(20)),batch_rows=5)
 assert ds.pair_count==20 and _counts(db)==(20,1)


def test_duplicate_pair_id_across_chunks_rejects_whole_batch(db):
 with __import__("pytest").raises(Exception) as exc:
  dataset_service.create_streaming(db,"b3","kPa","kPa","",io.BytesIO(_csv(20,dup_at=12,dup_of=3)),batch_rows=5)
 assert "跨分块重复" in str(getattr(exc.value,"detail",exc.value))
 assert _counts(db)==(0,0)
 retried=dataset_service.create_streaming(db,"b3","kPa","kPa","",io.BytesIO(_csv(20)),batch_rows=5)
 assert retried.pair_count==20


def test_in_chunk_duplicate_reports_source_line(db):
 with __import__("pytest").raises(Exception) as exc:
  dataset_service.create_streaming(db,"b4","kPa","kPa","",io.BytesIO(_csv(10,dup_at=3,dup_of=1)),batch_rows=5)
 assert "第5行" in str(getattr(exc.value,"detail",exc.value))
 assert _counts(db)==(0,0)


def test_compute_writes_every_point_and_sample_is_bounded(db):
 from src.models.instrument import InstrumentPair
 from src.models.study import CalibrationStudy
 from src.models.run import CalibrationRun
 ds=dataset_service.create_streaming(db,"b5","kPa","kPa","",io.BytesIO(_csv(5000)),batch_rows=1000)
 db.add(InstrumentPair(id="ip5",name="ip5",x_serial="X",y_serial="Y",unit="kPa",description=""))
 db.add(CalibrationStudy(id="st5",name="st5",dataset_id=ds.id,instrument_id="ip5",variance_ratio=2.25,tolerance=2.))
 db.add(CalibrationRun(id="run5",study_id="st5",status="queued",result={},sample=[],progress=0,phase="",error=""))
 db.commit()
 run_service.compute(db,"run5")
 run=db.get(CalibrationRun,"run5")
 assert run.status=="completed",run.error
 assert run.result["n"]==5000
 assert count_points(db,RunPoint,"run5")==5000
 assert count_points(db,RunPoint,"run5",outside=True)==run.result["agreement"]["outside_loa"]
 assert len(run.sample)==run.result["sample_size"]<=600
 assert run.result["sample_size"]<run.result["n"]


def test_json_endpoint_keeps_legacy_5000_row_limit(db):
 from src.schemas.dataset import DatasetCreate
 class Body(DatasetCreate):
  pass
 body=Body(name="json-batch",x_unit="kPa",y_unit="kPa",csv_text="pair_id,range_label,x,y\n"+"\n".join(f"J{i},low,{i},{i+1}" for i in range(5001)))
 with __import__("pytest").raises(Exception) as exc:
  dataset_service.create(db,body)
 assert "5000" in str(getattr(exc.value,"detail",exc.value))
 assert _counts(db)==(0,0)
 small=Body(name="json-small",x_unit="kPa",y_unit="kPa",csv_text="pair_id,range_label,x,y\n"+"\n".join(f"J{i},low,{i},{i+1}" for i in range(10)))
 row=dataset_service.create(db,small)
 assert row.pair_count==10 and row.status=="ready" and len(row.pairs)==10
