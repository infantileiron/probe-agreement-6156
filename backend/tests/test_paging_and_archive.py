import csv,io
import pytest
from sqlalchemy import select

from src.models.dataset import PairedDataset
from src.models.instrument import InstrumentPair
from src.models.study import CalibrationStudy
from src.models.run import CalibrationRun
from src.models.review import BiasReview
from src.models.report import Report
from src.models.point import ReportPoint,RunPoint
from src.services import dataset_service,report_service,review_service,run_service
from src.services.report_service import iter_export
from src.services.stream_store import count_points,dataset_page,point_page


def _csv(n):
 lines=["pair_id,range_label,x,y"]
 for i in range(n):
  x=20+i*.01;y=x+.4+((i%23)-11)*.01+(3.0 if i%500==0 else 0)
  lines.append(f"P{i:05d},low,{x:.6f},{y:.6f}")
 return ("\n".join(lines)+"\n").encode()


def _prepare(db,n,batch_rows):
 ds=dataset_service.create_streaming(db,"ds","kPa","kPa","",io.BytesIO(_csv(n)),batch_rows=batch_rows)
 db.add(InstrumentPair(id="ip",name="ip",x_serial="X1",y_serial="Y1",unit="kPa",description=""))
 db.add(CalibrationStudy(id="st",name="st",dataset_id=ds.id,instrument_id="ip",variance_ratio=2.25,tolerance=2.))
 db.add(CalibrationRun(id="run",study_id="st",status="queued",result={},sample=[],progress=0,phase="",error=""))
 db.commit()
 run_service.compute(db,"run")
 return db.get(CalibrationRun,"run")


@pytest.mark.parametrize("n",[250,300,1000])
def test_paging_boundaries_have_no_gaps_or_repeats(db,n):
 ds=dataset_service.create_streaming(db,"ds","kPa","kPa","",io.BytesIO(_csv(n)),batch_rows=128)
 seen=[];after=0;pages=0;total=None
 while True:
  items,next_after,total=dataset_page(db,ds,after,100);pages+=1
  assert len(items)<=100
  seen.extend(item["pair_id"] for item in items)
  if next_after is None:break
  after=next_after
 assert len(seen)==n and len(set(seen))==n
 assert seen==[f"P{i:05d}" for i in range(n)]
 assert pages==(n+99)//100
 assert total==n


@pytest.mark.parametrize("limit",[1,7,100,999,1000])
def test_point_pages_cover_every_row_once(db,limit):
 run=_prepare(db,250,64)
 seen=[];after=0
 while True:
  items,next_after=point_page(db,RunPoint,run.id,after,limit)
  seen.extend(item["pair_id"] for item in items)
  if next_after is None:break
  after=next_after
 assert len(seen)==250 and len(set(seen))==250
 assert count_points(db,RunPoint,run.id)==250


def test_outside_filter_paging_matches_counters(db):
 run=_prepare(db,600,100)
 flagged=run.result["agreement"]["outside_loa"]
 assert count_points(db,RunPoint,run.id,outside=True)==flagged
 seen=[];after=0
 while True:
  items,next_after=point_page(db,RunPoint,run.id,after,17,outside=True)
  seen.extend(items)
  if next_after is None:break
  after=next_after
 assert len(seen)==flagged and all(item["outside_loa"] for item in seen)
 assert len({item["pair_id"] for item in seen})==flagged


def test_report_archive_keeps_all_points_and_flags(db):
 run=_prepare(db,700,100)
 review=BiasReview(id="rv",run_id=run.id,action="复核说明，足够长",state="approved",reviewer="admin@probe.demo")
 db.add(review);db.commit()
 class Body:review_id="rv";title="归档底稿"
 report=report_service.create(db,Body())
 assert count_points(db,ReportPoint,report.id)==700
 assert report.snapshot["result"]["points_in_report"]==700
 # flags survive the copy
 run_flags=count_points(db,RunPoint,run.id,outside=True)
 report_flags=count_points(db,ReportPoint,report.id,outside=True)
 assert run_flags==report_flags==run.result["agreement"]["outside_loa"]
 # export rows == input rows, with the same pair ids and original readings
 text="".join(iter_export(db,report))
 rows=list(csv.DictReader(io.StringIO(text.lstrip("﻿"))))
 assert len(rows)==700
 assert [row["pair_id"] for row in rows]==[f"P{i:05d}" for i in range(700)]
 original={f"P{i:05d}":round(20+i*.01,6) for i in range(700)}
 for row in rows:assert abs(float(row["x"])-original[row["pair_id"]])<1e-9
 assert sum(row["outside_loa"]=="True" for row in rows)==run.result["agreement"]["outside_loa"]
 assert sum(row["outside_tolerance"]=="True" for row in rows)==run.result["outside_tolerance"]


def test_repeated_archive_returns_same_snapshot(db):
 run=_prepare(db,120,50)
 db.add(BiasReview(id="rv",run_id=run.id,action="复核说明，足够长",state="approved",reviewer="admin@probe.demo"));db.commit()
 class Body:review_id="rv";title="归档底稿"
 first=report_service.create(db,Body())
 second=report_service.create(db,Body())
 assert first.id==second.id
 assert count_points(db,ReportPoint,first.id)==120


def test_legacy_json_batch_still_computes_and_archives(db):
 pairs=[{"pair_id":f"L{i:03d}","range_label":"low","x":10+i*.02,"y":10.2+i*.02} for i in range(240)]
 db.add(PairedDataset(id="legacy",name="legacy",x_unit="kPa",y_unit="kPa",pairs=pairs,description="",pair_count=240))
 db.add(InstrumentPair(id="ip",name="ip",x_serial="X1",y_serial="Y1",unit="kPa",description=""))
 db.add(CalibrationStudy(id="st",name="st",dataset_id="legacy",instrument_id="ip",variance_ratio=2.25,tolerance=2.))
 db.add(CalibrationRun(id="runL",study_id="st",status="queued",result={},sample=[],progress=0,phase="",error=""))
 db.commit()
 run_service.compute(db,"runL")
 run=db.get(CalibrationRun,"runL")
 assert run.status=="completed",run.error
 assert run.result["n"]==240 and count_points(db,RunPoint,"runL")==240
 db.add(BiasReview(id="rvL",run_id="runL",action="旧批次复核说明，足够长",state="approved",reviewer="admin@probe.demo"));db.commit()
 class Body:review_id="rvL";title="旧批次底稿"
 report=report_service.create(db,Body())
 rows=list(csv.DictReader(io.StringIO("".join(iter_export(db,report)).lstrip("﻿"))))
 assert len(rows)==240


def test_legacy_report_without_point_rows_exports_snapshot(db):
 snapshot={"result":{"unit":"kPa","n":2,"points":[{"pair_id":"a","range_label":"low","x":1,"y":2,"mean":1.5,"difference":1,"fitted_y":1.9,"residual_y":.1,"outside_loa":False,"outside_tolerance":False},{"pair_id":"b","range_label":"high","x":2,"y":3,"mean":2.5,"difference":1,"fitted_y":2.9,"residual_y":.1,"outside_loa":True,"outside_tolerance":True}]},"action":"旧说明","reviewer":"admin"}
 db.add(Report(id="old",review_id="old-rv",title="旧报告",snapshot=snapshot));db.commit()
 rows=list(csv.DictReader(io.StringIO("".join(iter_export(db,db.get(Report,"old"))).lstrip("﻿"))))
 assert [row["pair_id"] for row in rows]==["a","b"]
 assert rows[1]["outside_loa"]=="True"
