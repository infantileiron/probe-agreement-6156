from uuid import uuid4
from fastapi import HTTPException
from ..models.run import CalibrationRun
from ..models.study import CalibrationStudy
from ..models.dataset import PairedDataset
from ..models.instrument import InstrumentPair
from ..models.point import RunPoint
from ..utils.queue import enqueue
from .deming import regress_from_moments
from .agreement import agreement_from_moments
from .paired_data import CHUNK_ROWS
from .stream_store import clear_points,dataset_pair_count,insert_points,iter_dataset_readings
from .stream_stats import DetailPass,MomentPass,MomentPass2,proportional_from_moments,safe_sqrt

# Progress commits are bounded so the worker does not churn the database.
PROGRESS_STEP=20


def create(db,body):
 if not db.get(CalibrationStudy,body.study_id):raise HTTPException(422,"校准研究不存在")
 row=CalibrationRun(id=str(uuid4()),study_id=body.study_id,status="queued",result={},sample=[],progress=0,phase="",error="");db.add(row);db.commit()
 try:enqueue(row.id)
 except Exception:
  row.status="failed";row.error="Redis队列不可用，请稍后重试";db.commit();raise HTTPException(503,row.error)
 return row


def compute(db,run_id):
 row=db.get(CalibrationRun,run_id)
 if row is None or row.status not in ["queued","running"]:return
 row.status="running";row.error="";row.phase="counting";row.progress=0;db.commit()
 try:
  study=db.get(CalibrationStudy,row.study_id);dataset=db.get(PairedDataset,study.dataset_id);pair=db.get(InstrumentPair,study.instrument_id)
  if dataset is None or dataset.status!="ready":raise ValueError("配对批次不可用")
  if pair is None:raise ValueError("探头组合不存在")
  if dataset.x_unit!=dataset.y_unit or dataset.x_unit!=pair.unit:raise ValueError("单位不一致")
  _check_study(study)
  first=MomentPass();total=dataset_pair_count(db,dataset);seen=0
  for batch in iter_dataset_readings(db,dataset):
   first.add(batch);seen+=len(batch);_progress(db,row,seen,total,PROGRESS_STEP)
  n,mx,my=first.finish()
  row.phase="centring";row.progress=0;db.commit()
  second=MomentPass2(mx,my);seen=0
  for batch in iter_dataset_readings(db,dataset):
   second.add(batch);seen+=len(batch);_progress(db,row,seen,total,PROGRESS_STEP)
  moments=second.finish()
  deming=regress_from_moments(n,mx,my,moments["vx"],moments["vy"],moments["cov"],study.variance_ratio)
  total_ss=moments["total_ss"];sample_sd=safe_sqrt(total_ss/(n-1));bias=my-mx
  proportional=proportional_from_moments(bias,second.mm,total_ss,moments["ss_m"],moments["cov_md"])
  # BA limits depend only on bias and sample SD, so markings are known up front.
  low=bias-1.96*sample_sd;high=bias+1.96*sample_sd
  detail=DetailPass(n,deming["slope"],deming["intercept"],bias,low,high,study.tolerance,proportional)
  clear_points(db,RunPoint,row.id);db.commit()
  row.phase="marking";row.progress=0;db.commit()
  seen=0
  for batch in iter_dataset_readings(db,dataset):
   rows=detail.add(batch);insert_points(db,RunPoint,row.id,rows)
   seen+=len(rows);_progress(db,row,seen,total,PROGRESS_STEP)
  proportional["r_squared"]=_r_squared(detail.proportional_sse(),total_ss)
  sample=detail.finalize_sample()
  agreement=agreement_from_moments(n,bias,sample_sd,second.mm,total_ss,moments["ss_m"],moments["cov_md"],detail.outside_loa,proportional=proportional)
  deming["residual_rmse_y"]=detail.rmse()
  row.result={
   "dataset_name":dataset.name,"instrument_name":pair.name,"x_serial":pair.x_serial,"y_serial":pair.y_serial,
   "unit":pair.unit,"n":n,"deming":deming,"agreement":agreement,"tolerance":study.tolerance,
   "outside_tolerance":detail.outside_tolerance,"sample_size":len(sample),
   "sample_note":"图表为等步长抽样并补充前若干越界配对；统计与计数使用全部读数。",
  }
  row.sample=sample;row.progress=n;row.phase="completed";row.status="completed"
 except Exception as e:
  row.status="failed";row.phase="failed";row.error=str(e)[:1000]
  try:
   db.rollback();clear_points(db,RunPoint,row.id);db.commit()
  except Exception:db.rollback()
 db.commit()


def _r_squared(residual_sse,total_ss):
 if residual_sse is None or total_ss==0:return None
 return max(0.,min(1.,1-residual_sse/total_ss))


def _check_study(study):
 if not study:raise ValueError("校准研究不存在")
 for value,label in ((study.variance_ratio,"lambda"),(study.tolerance,"容差")):
  if value is None or not (value>0) or value!=value or value in (float("inf"),float("-inf")):raise ValueError(f"{label}须为正且有限")


def _progress(db,row,seen,total,step):
 """Persist the current phase's row count at most every ``step`` chunks.

 ``progress`` always counts rows finished in the current phase; ``result.n``
 is the final authority. Committing in chunks keeps peers reading bounded.
 """
 if seen==0 or seen>=total or seen-row.progress>=step*CHUNK_ROWS:
  row.progress=seen;db.commit()
