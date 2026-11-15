from sqlalchemy import select
from ..services import run_service
from ..models.run import CalibrationRun
from ..models.common import serialize
from .common import require
RESULT_KEYS=("dataset_name","instrument_name","x_serial","y_serial","unit","n","deming","agreement","tolerance","outside_tolerance","sample_size","sample_note")
def list_all(db):
 """Run list carries aggregates only.

 The chart sample and per-pair detail are fetched from /runs/{id}/sample and
 /runs/{id}/points so a million-pair run never bloats the collection.
 """
 rows=[]
 for ident in db.scalars(select(CalibrationRun.id).order_by(CalibrationRun.created_at.desc()).limit(200)).all():
  row=require(db,CalibrationRun,ident);data=serialize(row)
  result=data.get("result") or {}
  data["result"]={key:result[key] for key in RESULT_KEYS if key in result}
  data.pop("sample",None)
  rows.append(data)
 return rows
def detail(db,ident):
 row=require(db,CalibrationRun,ident);data=serialize(row)
 data["result"]={key:(row.result or {}).get(key) for key in RESULT_KEYS if key in (row.result or {})}
 data.pop("sample",None)
 return data
def create(db,body):return serialize(run_service.create(db,body))
