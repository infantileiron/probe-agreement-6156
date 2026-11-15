from uuid import uuid4
from sqlalchemy import delete,select
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from ..models.dataset import PairedDataset
from ..models.reading import PairedReading
from .paired_data import CHUNK_ROWS,RowError,parse_csv,rows_from

# Imports larger than this use the streaming endpoint; the JSON endpoint keeps
# its original 5000-row contract for API compatibility.
LEGACY_LIMIT=5000
IMPORTING="importing"
READY="ready"


def create(db,body):
 if db.scalar(select(PairedDataset).where(PairedDataset.name==body.name)):raise HTTPException(409,"配对批次名称已存在")
 try:pairs=parse_csv(body.csv_text)
 except ValueError as e:raise HTTPException(422,str(e))
 row=PairedDataset(id=str(uuid4()),name=body.name,x_unit=body.x_unit,y_unit=body.y_unit,pairs=pairs,description=body.description,pair_count=len(pairs),status=READY);db.add(row);db.commit();return row


def create_streaming(db,name,x_unit,y_unit,description,stream,batch_rows=CHUNK_ROWS):
 """Import a CSV of any size into paired_readings in bounded chunks.

 Chunks are committed as they are read, but the batch is created with status
 "importing" and is flipped to "ready" only after the last chunk. Every read
 path filters on "ready", so a malformed row or a duplicate pair_id (in-chunk,
 or across chunks via UNIQUE(dataset_id,pair_id)) leaves the whole batch
 invisible. The failed import is cleaned up in the same call so the name can be
 retried immediately; a leftover "importing" row from a crashed process is
 swept before a retry with the same name.

 Memory is bounded by ``batch_rows`` and the in-chunk duplicate set; the input
 stream is read incrementally and never materialised.
 """
 stale=db.scalar(select(PairedDataset).where(PairedDataset.name==name))
 if stale is not None:
  if stale.status!=IMPORTING:raise HTTPException(409,"配对批次名称已存在")
  _discard(db,stale)
 dataset_id=str(uuid4())
 try:
  dataset=PairedDataset(id=dataset_id,name=name,x_unit=x_unit,y_unit=y_unit,pairs=[],description=description,pair_count=0,status=IMPORTING)
  db.add(dataset)
  try:db.commit()
  except IntegrityError:
   db.rollback();raise HTTPException(409,"配对批次名称已存在") from None
  inserted=0;batch=[];seen=set()
  for reading in rows_from(stream):
   if reading.pair_id in seen:raise RowError(reading.line,"配对ID重复")
   seen.add(reading.pair_id)
   batch.append({"dataset_id":dataset_id,"pair_id":reading.pair_id,"range_label":reading.range_label,"x":reading.x,"y":reading.y});inserted+=1
   if len(batch)>=batch_rows:_insert(db,batch);db.commit();batch=[];seen=set()
  if batch:_insert(db,batch);db.commit()
  if inserted<4:raise ValueError("至少需要4组完整配对")
  dataset=db.get(PairedDataset,dataset_id);dataset.pair_count=inserted;dataset.status=READY;db.commit();return dataset
 except RowError as e:
  _fail(db,dataset_id);raise HTTPException(422,str(e)) from None
 except ValueError as e:
  _fail(db,dataset_id);raise HTTPException(422,str(e)) from None
 except HTTPException:
  _fail(db,dataset_id);raise
 except IntegrityError:
  _fail(db,dataset_id);raise HTTPException(422,"配对ID跨分块重复，整批未导入，可修正后重试") from None
 except Exception:
  _fail(db,dataset_id);raise


def _insert(db,rows):db.execute(PairedReading.__table__.insert(),rows)


def _fail(db,dataset_id):
 try:db.rollback()
 except Exception:pass
 row=db.get(PairedDataset,dataset_id)
 if row is not None:_discard(db,row)


def _discard(db,row):
 """Delete an invisible batch and all its staged readings."""
 try:
  db.execute(delete(PairedReading).where(PairedReading.dataset_id==row.id))
  db.delete(row);db.commit()
 except Exception:db.rollback()
