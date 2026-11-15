from sqlalchemy import select
from ..services import report_service
from ..models.report import Report
from ..models.common import serialize
from .common import require
LIST_KEYS=("dataset_name","instrument_name","unit","n","deming","agreement","tolerance","outside_tolerance","sample_size","points_in_report")
def list_all(db):
 rows=[]
 for ident in db.scalars(select(Report.id).order_by(Report.created_at.desc()).limit(200)).all():
  data=serialize(require(db,Report,ident));snapshot=data.get("snapshot") or {}
  result=snapshot.get("result") or {}
  data["snapshot"]={"result":{key:result[key] for key in LIST_KEYS if key in result},"action":snapshot.get("action"),"reviewer":snapshot.get("reviewer"),"run_id":snapshot.get("run_id"),"points_in_report":snapshot.get("points_in_report",0)}
  rows.append(data)
 return rows
def detail(db,ident):return serialize(require(db,Report,ident))
def create(db,body):
 row=report_service.create(db,body);data=serialize(row)
 data["snapshot"]={"result":{key:(row.snapshot.get("result") or {}).get(key) for key in LIST_KEYS if key in (row.snapshot.get("result") or {})},"action":row.snapshot.get("action"),"reviewer":row.snapshot.get("reviewer"),"run_id":row.snapshot.get("run_id"),"points_in_report":row.snapshot.get("points_in_report",0)}
 return data
