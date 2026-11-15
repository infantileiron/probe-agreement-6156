from fastapi import HTTPException
from sqlalchemy import select
from ..models.common import serialize
from ..models.dataset import PairedDataset
READY="ready"
def listing(db,cls,max_rows=200):
 ids=db.scalars(select(cls.id).order_by(cls.created_at.desc()).limit(max_rows)).all()
 return [serialize(db.get(cls,ident)) for ident in ids]
def require(db,cls,ident):
 row=db.get(cls,ident)
 if row is None:raise HTTPException(404,"记录不存在")
 return row
def require_dataset(db,ident):
 row=db.get(PairedDataset,ident)
 if row is None or row.status!=READY:raise HTTPException(404,"记录不存在")
 return row
def dataset_ids(db,max_rows=200):
 return db.scalars(select(PairedDataset.id).where(PairedDataset.status==READY).order_by(PairedDataset.created_at.desc()).limit(max_rows)).all()
def dataset_summary(db,row):
 """List/detail projection that never ships the full per-pair payload."""
 from ..services.stream_store import dataset_pair_count
 data=serialize(row)
 data["pairs"]=list(row.pairs[:16]) if row.pairs else []
 data["pair_count"]=dataset_pair_count(db,row)
 data["has_legacy_pairs"]=bool(row.pairs)
 return data
