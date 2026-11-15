from fastapi import APIRouter,Depends,Query
from ..config.database import get_db
from ..utils.auth import current,write_user
from ..schemas.run import RunCreate
from ..controllers import run_controller as controller,common
from ..models.run import CalibrationRun
from ..models.point import RunPoint
from ..services.stream_store import PAGE_DEFAULT,PAGE_MAX,count_points,point_page
router=APIRouter(prefix="/runs",tags=["runs"])
@router.get("")
def listing(db=Depends(get_db),user=Depends(current)):return controller.list_all(db)
@router.get("/{ident}")
def detail(ident:str,db=Depends(get_db),user=Depends(current)):return controller.detail(db,ident)
@router.get("/{ident}/points")
def points(ident:str,after:int=Query(default=0,ge=0),limit:int=Query(default=PAGE_DEFAULT,ge=1,le=PAGE_MAX),outside:bool|None=Query(default=None),db=Depends(get_db),user=Depends(current)):
 row=common.require(db,CalibrationRun,ident)
 items,next_after=point_page(db,RunPoint,row.id,after,limit,outside)
 return {"items":items,"next_after":next_after,"total":count_points(db,RunPoint,row.id,outside),"after":after,"limit":limit,"outside_only":outside}
@router.get("/{ident}/sample")
def sample(ident:str,db=Depends(get_db),user=Depends(current)):
 row=common.require(db,CalibrationRun,ident);result=row.result or {}
 return {"items":row.sample or [],"sample_size":len(row.sample or []),"n":result.get("n",0),"note":result.get("sample_note","图表为等步长抽样；统计与计数使用全部读数。")}
@router.post("",status_code=201)
def create(body:RunCreate,db=Depends(get_db),user=Depends(write_user)):return controller.create(db,body)
