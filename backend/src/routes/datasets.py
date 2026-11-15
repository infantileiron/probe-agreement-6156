import tempfile
from fastapi import APIRouter,Depends,HTTPException,Query,Request
from fastapi.concurrency import run_in_threadpool
from ..config.database import get_db
from ..utils.auth import current,write_user
from ..schemas.dataset import DatasetCreate,check_units
from ..controllers import dataset_controller as controller,common
from ..services import dataset_service
from ..services.stream_store import PAGE_DEFAULT,PAGE_MAX,dataset_page
router=APIRouter(prefix="/datasets",tags=["datasets"])
@router.get("")
def listing(db=Depends(get_db),user=Depends(current)):return controller.list_all(db)
@router.get("/{ident}")
def detail(ident:str,db=Depends(get_db),user=Depends(current)):return controller.detail(db,ident)
@router.get("/{ident}/pairs")
def pairs(ident:str,after:int=Query(default=0,ge=0),limit:int=Query(default=PAGE_DEFAULT,ge=1,le=PAGE_MAX),db=Depends(get_db),user=Depends(current)):
 row=common.require_dataset(db,ident);items,next_after,total=dataset_page(db,row,after,limit)
 return {"items":items,"next_after":next_after,"total":total,"after":after,"limit":limit}
@router.post("",status_code=201)
def create(body:DatasetCreate,db=Depends(get_db),user=Depends(write_user)):return controller.create(db,body)
@router.post("/import",status_code=201)
async def import_csv(request:Request,name:str=Query(min_length=2,max_length=180),x_unit:str=Query(),y_unit:str=Query(),description:str=Query(default="",max_length=2000),db=Depends(get_db),user=Depends(write_user)):
 """Stream a CSV request body into paired_readings in bounded chunks.

 The body is spooled (memory up to 8 MiB, then a temporary file) so the request
 itself never holds a million-row payload in memory. The batch only becomes
 visible after its final chunk commits; a bad row or a cross-chunk duplicate
 leaves nothing listed, and the same name can be retried.
 """
 try:check_units(x_unit,y_unit)
 except ValueError as e:raise HTTPException(422,str(e))
 with tempfile.SpooledTemporaryFile(max_size=8*1024*1024) as spool:
  async for chunk in request.stream():spool.write(chunk)
  spool.seek(0)
  row=await run_in_threadpool(dataset_service.create_streaming,db,name.strip(),x_unit,y_unit,description,spool)
 return common.dataset_summary(db,row)
from ..schemas.dataset import DatasetEdit
@router.patch("/{ident}")
def edit(ident:str,body:DatasetEdit,db=Depends(get_db),user=Depends(write_user)):
 row=common.require_dataset(db,ident);row.description=body.description;db.commit();return common.dataset_summary(db,row)
