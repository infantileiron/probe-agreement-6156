from fastapi import APIRouter,Depends,HTTPException,Query
from fastapi.responses import StreamingResponse
from ..config.database import Session,get_db
from ..utils.auth import current,admin
from ..schemas.report import ReportCreate
from ..controllers import report_controller as controller,common
from ..models.report import Report
from ..models.point import ReportPoint
from ..services.report_service import iter_export
from ..services.stream_store import PAGE_DEFAULT,PAGE_MAX,count_points,point_page
router=APIRouter(prefix="/reports",tags=["reports"])
@router.get("")
def listing(db=Depends(get_db),user=Depends(current)):return controller.list_all(db)
@router.get("/{ident}")
def detail(ident:str,db=Depends(get_db),user=Depends(current)):return controller.detail(db,ident)
@router.get("/{ident}/points")
def points(ident:str,after:int=Query(default=0,ge=0),limit:int=Query(default=PAGE_DEFAULT,ge=1,le=PAGE_MAX),db=Depends(get_db),user=Depends(current)):
 row=common.require(db,Report,ident)
 items,next_after=point_page(db,ReportPoint,row.id,after,limit)
 return {"items":items,"next_after":next_after,"total":count_points(db,ReportPoint,row.id),"after":after,"limit":limit}
@router.post("",status_code=201)
def create(body:ReportCreate,db=Depends(get_db),user=Depends(admin)):return controller.create(db,body)
@router.get("/{ident}/csv")
def download(ident:str,user=Depends(current)):
 # The export owns its session: request-scoped sessions close before a streamed
 # body is fully sent.
 with Session() as db:
  if db.get(Report,ident) is None:raise HTTPException(404,"记录不存在")
 return StreamingResponse(_rows(ident),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=probe-calibration.csv"})
def _rows(ident):
 with Session() as db:
  row=db.get(Report,ident)
  if row is not None:yield from iter_export(db,row)
