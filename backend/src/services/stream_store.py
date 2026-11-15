"""Bounded-memory helpers shared by import, calibration and archive export.

Every reader here is keyset paginated by the auto-increment key. For a dataset
or run those keys follow source insertion order, so pages neither skip nor
repeat rows.
"""
from sqlalchemy import delete,func,insert,select

from ..models.point import ReportPoint,RunPoint
from ..models.reading import PairedReading
from .paired_data import CHUNK_ROWS,Reading

PAGE_MAX=1000
PAGE_DEFAULT=100


def chunked(values,size=CHUNK_ROWS):
 batch=[]
 for value in values:
  batch.append(value)
  if len(batch)>=size:
   yield batch;batch=[]
 if batch:yield batch


def _legacy_chunks(pairs,size=CHUNK_ROWS):
 for batch in chunked(pairs,size):
  yield [Reading(p.get("pair_id",""),p.get("range_label",""),p["x"],p["y"],index+2) for index,p in enumerate(batch)]


def iter_dataset_readings(db,dataset,size=CHUNK_ROWS):
 """Yield Reading batches for a dataset.

 New imports are read from paired_readings with a keyset cursor; legacy batches
 keep their original <=5000-row JSON payload and are streamed from it.
 """
 if dataset.pairs:
  yield from _legacy_chunks(dataset.pairs,size);return
 last=0
 while True:
  rows=db.execute(select(PairedReading.id,PairedReading.pair_id,PairedReading.range_label,PairedReading.x,PairedReading.y).where(PairedReading.dataset_id==dataset.id,PairedReading.id>last).order_by(PairedReading.id).limit(size)).all()
  if not rows:return
  last=rows[-1][0]
  yield [Reading(row[1],row[2],row[3],row[4]) for row in rows]


def dataset_pair_count(db,dataset):
 if dataset.pairs:return len(dataset.pairs)
 return db.scalar(select(func.count()).select_from(PairedReading).where(PairedReading.dataset_id==dataset.id)) or 0


def dataset_page(db,dataset,after=0,limit=PAGE_DEFAULT):
 """One page of original readings; returns (items,next_after,total)."""
 total=dataset_pair_count(db,dataset)
 if dataset.pairs:
  start=max(int(after or 0),0);items=dataset.pairs[start:start+limit]
  end=start+len(items);return items,(end if end<total else None),total
 # Fetch one extra row to know whether another page exists; this keeps the
 # final exact-multiple page from producing an empty trailing page.
 rows=db.execute(select(PairedReading.id,PairedReading.pair_id,PairedReading.range_label,PairedReading.x,PairedReading.y).where(PairedReading.dataset_id==dataset.id,PairedReading.id>int(after or 0)).order_by(PairedReading.id).limit(limit+1)).all()
 more=len(rows)>limit;rows=rows[:limit]
 items=[{"id":row[0],"pair_id":row[1],"range_label":row[2],"x":row[3],"y":row[4]} for row in rows]
 return items,(rows[-1][0] if more and rows else None),total


_POINTS={RunPoint:"run_id",ReportPoint:"report_id"}


def _owner_col(model):return getattr(model,_POINTS[model])


def clear_points(db,model,owner_id):
 db.execute(delete(model).where(_owner_col(model)==owner_id))


def insert_points(db,model,owner_id,rows):
 if rows:db.execute(insert(model),[dict(row,**{_POINTS[model]:owner_id}) for row in rows])


def count_points(db,model,owner_id,outside=None):
 query=select(func.count()).select_from(model).where(_owner_col(model)==owner_id)
 if outside is True:query=query.where(model.outside_loa.is_(True))
 elif outside is False:query=query.where(model.outside_loa.is_(False))
 return db.scalar(query) or 0


POINT_COLUMNS=("pair_id","range_label","x","y","mean","difference","fitted_y","residual_y","outside_loa","outside_tolerance")


def _point_dict(model,row):
 return {"id":row[0],"pair_id":row[1],"range_label":row[2],"x":row[3],"y":row[4],"mean":row[5],"difference":row[6],"fitted_y":row[7],"residual_y":row[8],"outside_loa":bool(row[9]),"outside_tolerance":bool(row[10])}


def point_page(db,model,owner_id,after=0,limit=PAGE_DEFAULT,outside=None):
 columns=(model.id,model.pair_id,model.range_label,model.x,model.y,model.mean,model.difference,model.fitted_y,model.residual_y,model.outside_loa,model.outside_tolerance)
 query=select(*columns).where(_owner_col(model)==owner_id,model.id>int(after or 0))
 if outside is True:query=query.where(model.outside_loa.is_(True))
 elif outside is False:query=query.where(model.outside_loa.is_(False))
 rows=db.execute(query.order_by(model.id).limit(limit+1)).all()
 more=len(rows)>limit;rows=rows[:limit]
 return [_point_dict(model,row) for row in rows],(rows[-1][0] if more and rows else None)


def in_chunks(db,model,owner_id,size=CHUNK_ROWS):
 """Yield archived point dicts in bounded pages (used by CSV streaming)."""
 last=0
 while True:
  rows=db.execute(select(*_point_columns(model)).where(_owner_col(model)==owner_id,model.id>last).order_by(model.id).limit(size)).all()
  if not rows:return
  last=rows[-1][0]
  for row in rows:
   item=_point_dict(model,row);item.pop("id",None);yield item


def _point_columns(model):
 return (model.id,model.pair_id,model.range_label,model.x,model.y,model.mean,model.difference,model.fitted_y,model.residual_y,model.outside_loa,model.outside_tolerance)
