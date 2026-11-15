"""Run one stage in-process and report its peak RSS in MiB.

Used by the acceptance harness so import and calibration peaks are measured in
the process that actually does the work, not in a parent shell.
"""
import argparse,importlib,json,os,resource,sys,time
from pathlib import Path

BACKEND=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BACKEND))


def peak_mib():
 return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024


def main():
 parser=argparse.ArgumentParser()
 parser.add_argument("stage",choices=["import","compute","archive","export","sample-check"])
 parser.add_argument("--csv")
 parser.add_argument("--name",default="million-row batch")
 parser.add_argument("--unit",default="kPa")
 parser.add_argument("--lambda-ratio",dest="variance_ratio",type=float,default=2.25)
 parser.add_argument("--tolerance",type=float,default=2.)
 parser.add_argument("--batch-rows",type=int,default=5000)
 parser.add_argument("--report-id")
 parser.add_argument("--out")
 parser.add_argument("--rows",type=int)
 args=parser.parse_args()

 from src.config.database import Session,initialize
 initialize()
 import src.models  # noqa: F401
 peak_start=peak_mib();started=time.time();summary={}
 with Session() as db:
  if args.stage=="import":
   from src.services.dataset_service import create_streaming
   with open(args.csv,"rb") as handle:
    dataset=create_streaming(db,args.name,args.unit,args.unit,"百万行验收",handle,batch_rows=args.batch_rows)
   summary={"dataset_id":dataset.id,"pair_count":dataset.pair_count,"status":dataset.status,"batch_rows":args.batch_rows}
  elif args.stage=="compute":
   from src.models.dataset import PairedDataset
   from src.models.instrument import InstrumentPair
   from src.models.study import CalibrationStudy
   from src.models.run import CalibrationRun
   from src.services.run_service import compute
   dataset=db.query(PairedDataset).filter_by(name=args.name).one()
   pair=db.query(InstrumentPair).filter_by(name="验收探头组合").first()
   if pair is None:
    pair=InstrumentPair(id="accept-pair",name="验收探头组合",x_serial="JQ-P17",y_serial="JQ-P18",unit=args.unit,description="")
    db.add(pair);db.commit()
   study=db.query(CalibrationStudy).filter_by(name="百万行校准研究").first()
   if study is None:
    study=CalibrationStudy(id="accept-study",name="百万行校准研究",dataset_id=dataset.id,instrument_id=pair.id,variance_ratio=args.variance_ratio,tolerance=args.tolerance)
    db.add(study);db.commit()
   run=db.query(CalibrationRun).filter_by(study_id=study.id).order_by(CalibrationRun.created_at.desc()).first()
   if run is None:
    run=CalibrationRun(id="accept-run",study_id=study.id,status="queued",result={},sample=[],progress=0,phase="",error="")
    db.add(run);db.commit()
   run.status="queued";db.commit()
   compute(db,run.id);db.refresh(run)
   from src.services.stream_store import count_points
   from src.models.point import RunPoint,ReportPoint
   summary={"run_id":run.id,"status":run.status,"error":run.error,"n":run.result.get("n"),
            "points":count_points(db,RunPoint,run.id),"sample_size":len(run.sample or []),
            "outside_loa":run.result.get("agreement",{}).get("outside_loa"),
            "outside_tolerance":run.result.get("outside_tolerance"),
            "deming":run.result.get("deming"),"bias_sd":{k:run.result.get("agreement",{}).get(k) for k in ("bias","sample_sd","loa_low","loa_high")}}
  elif args.stage=="archive":
   from src.models.run import CalibrationRun
   from src.models.review import BiasReview
   from src.models.report import Report
   from src.services.report_service import create as create_report
   run=db.query(CalibrationRun).order_by(CalibrationRun.created_at.desc()).first()
   if run is None or run.status!="completed":raise SystemExit("run not completed; run compute first")
   review=db.query(BiasReview).filter_by(run_id=run.id).first()
   if review is None:
    review=BiasReview(id="accept-review",run_id=run.id,action="百万行验收：复核比例偏倚与越界配对，结论不据此宣称可互换。",state="approved",reviewer="admin@probe.demo")
    db.add(review);db.commit()
   class Body:review_id=review.id;title="百万行校准底稿"
   report=create_report(db,Body());db.refresh(report)
   from src.services.stream_store import count_points
   from src.models.point import ReportPoint
   summary={"report_id":report.id,"points_in_report":count_points(db,ReportPoint,report.id),"n":report.snapshot["result"]["n"],"outside_loa":report.snapshot["result"]["agreement"]["outside_loa"]}
  elif args.stage=="export":
   from src.models.report import Report
   from src.services.report_service import iter_export
   report=db.get(Report,args.report_id)
   out=Path(args.out) if args.out else Path("/tmp/export.csv")
   lines=0
   with out.open("w",encoding="utf-8",newline="") as handle:
    for piece in iter_export(db,report):
     handle.write(piece);lines+=piece.count("\n")
   summary={"report_id":args.report_id,"output":str(out),"lines":lines,"bytes":out.stat().st_size}
  elif args.stage=="sample-check":
   from src.models.dataset import PairedDataset
   from src.models.run import CalibrationRun
   from src.models.point import RunPoint
   from src.services.stream_store import point_page
   dataset=db.query(PairedDataset).filter_by(name=args.name).one()
   run=db.query(CalibrationRun).order_by(CalibrationRun.created_at.desc()).first()
   # Verify coverage without holding a million ids in memory: pages must be
   # strictly ordered (no repeats) and the row count must equal both SQL
   # count(*) and count(distinct pair_id) for the run.
   import zlib
   rows=0;after=0;digest=0;pages=0;last=""
   ascending=True
   limit=1000
   while True:
    items,next_after=point_page(db,RunPoint,run.id,after,limit)
    if not items and next_after is None:break
    for item in items:
     if item["pair_id"]<=last:ascending=False
     last=item["pair_id"];rows+=1
     digest=zlib.crc32(f"{item['pair_id']}|{item['difference']:.9f}".encode(),digest)
    pages+=1
    if next_after is None:break
    after=next_after
   from sqlalchemy import func,select
   stored=db.scalar(select(func.count()).select_from(RunPoint).where(RunPoint.run_id==run.id))
   distinct=db.scalar(select(func.count(func.distinct(RunPoint.pair_id))).where(RunPoint.run_id==run.id))
   summary={"paged_rows":rows,"pages":pages,"page_size":limit,"digest":digest,"stored_rows":stored,
            "distinct_pair_ids":distinct,"strictly_ascending":ascending,"run_n":run.result["n"]}
 summary.update({"peak_mib":round(peak_mib(),1),"baseline_mib":round(peak_start,1),"seconds":round(time.time()-started,1),"rows_arg":args.rows})
 print(json.dumps(summary,ensure_ascii=False))


if __name__=="__main__":main()
