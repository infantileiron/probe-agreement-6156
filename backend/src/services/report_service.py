import csv,io
from uuid import uuid4
from sqlalchemy import select
from fastapi import HTTPException
from ..models.review import BiasReview
from ..models.run import CalibrationRun
from ..models.report import Report
from ..models.point import ReportPoint,RunPoint as RunPointRow
from .stream_store import count_points,in_chunks,insert_points

EXPORT_HEADER=["pair_id","range_label","x","y","unit","mean","difference_y_minus_x","deming_fitted_y","residual_y","outside_loa","outside_tolerance"]
EXPORT_BATCH=1000
# Reports keep a JSON copy of these small aggregates; per-pair rows go to
# report_points so million-row archives stay queryable and streamable.
SNAPSHOT_KEYS=("dataset_name","instrument_name","x_serial","y_serial","unit","n","deming","agreement","tolerance","outside_tolerance","sample_size","sample_note")


def create(db,body):
 review=db.get(BiasReview,body.review_id)
 if review is None or review.state!="approved":raise HTTPException(409,"报告必须关联已批准的偏倚复核")
 existing=db.scalar(select(Report).where(Report.review_id==body.review_id))
 if existing:return existing
 run=db.get(CalibrationRun,review.run_id)
 if run is None or run.status!="completed":raise HTTPException(409,"运行尚未完成，无法归档")
 row=Report(id=str(uuid4()),review_id=review.id,title=body.title,snapshot={"result":{key:run.result.get(key) for key in SNAPSHOT_KEYS if key in run.result},"action":review.action,"reviewer":review.reviewer,"run_id":run.id,"points_in_report":0})
 db.add(row);db.flush()
 _copy_points(db,run.id,row.id)
 # Mutate a copy: the JSON column may hold a plain dict, and re-assigning the
 # whole snapshot is what makes SQLAlchemy persist the count.
 snapshot=dict(row.snapshot);snapshot["result"]=dict(snapshot["result"])
 snapshot["result"]["points_in_report"]=count_points(db,ReportPoint,row.id)
 row.snapshot=snapshot
 db.commit();return row


def _copy_points(db,run_id,report_id):
 last=0
 while True:
  rows=db.execute(select(RunPointRow.id,RunPointRow.pair_id,RunPointRow.range_label,RunPointRow.x,RunPointRow.y,RunPointRow.mean,RunPointRow.difference,RunPointRow.fitted_y,RunPointRow.residual_y,RunPointRow.outside_loa,RunPointRow.outside_tolerance).where(RunPointRow.run_id==run_id,RunPointRow.id>last).order_by(RunPointRow.id).limit(EXPORT_BATCH)).all()
  if not rows:return
  last=rows[-1][0]
  insert_points(db,ReportPoint,report_id,[{"pair_id":r[1],"range_label":r[2],"x":r[3],"y":r[4],"mean":r[5],"difference":r[6],"fitted_y":r[7],"residual_y":r[8],"outside_loa":bool(r[9]),"outside_tolerance":bool(r[10])} for r in rows])


def export(row):
 """Legacy in-memory export for <=5000-row snapshots (kept for compatibility)."""
 out=io.StringIO();writer=csv.writer(out);writer.writerow(EXPORT_HEADER)
 result=row.snapshot["result"]
 for p in result.get("points",[]):writer.writerow(_row(p,result["unit"]))
 return "﻿"+out.getvalue()


def iter_export(db,row):
 """Stream an archive CSV: one bounded page of report_points at a time.

 Works for both archived (report_points) and pre-migration reports whose
 per-pair rows live in snapshot.result.points.
 """
 out=io.StringIO();csv.writer(out).writerow(EXPORT_HEADER);yield "﻿"+out.getvalue()
 result=row.snapshot["result"];unit=result.get("unit","")
 if count_points(db,ReportPoint,row.id):
  out=io.StringIO();writer=csv.writer(out)
  for point in in_chunks(db,ReportPoint,row.id,EXPORT_BATCH):
   point["unit"]=unit;writer.writerow(_row(point,unit));yield out.getvalue();out.seek(0);out.truncate(0)
 else:
  out=io.StringIO();writer=csv.writer(out)
  for point in result.get("points",[]):
   writer.writerow(_row(point,unit))
  yield out.getvalue()


def _row(point,unit):
 return [point["pair_id"],point["range_label"],point["x"],point["y"],unit,point["mean"],point["difference"],point["fitted_y"],point["residual_y"],point["outside_loa"],point["outside_tolerance"]]
