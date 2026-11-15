import csv,io,math
from dataclasses import dataclass

BANDS=frozenset(("low","middle","high"))
MAX_PAIR_ID=80
MAX_ABS=1e9
# Rows validated per batch. Also the unit for progress reporting, so a 1,000,000
# row file never materialises more than one slice at a time.
CHUNK_ROWS=5000


@dataclass(slots=True)
class Reading:
 pair_id:str
 range_label:str
 x:float
 y:float
 line:int=0


class RowError(ValueError):
 """A CSV row failed validation. Carries a 1-based source line number."""
 def __init__(self,line,message):
  super().__init__(f"第{line}行{message}")
  self.line=line


def parse_csv(text):
 """Legacy whole-file parser retained for the original <=5000-row API contract."""
 rows=list(csv.DictReader(io.StringIO(text)));required={"pair_id","range_label","x","y"}
 if not rows or len(rows)>5000 or not required.issubset(rows[0]):raise ValueError("CSV需1至5000行并包含pair_id,range_label,x,y")
 seen=set();result=[]
 for index,row in enumerate(rows,2):
  ident=(row.get("pair_id") or "").strip();band=(row.get("range_label") or "").strip()
  if not ident or len(ident)>MAX_PAIR_ID or ident in seen:raise ValueError(f"第{index}行配对ID为空、过长或重复")
  if band not in BANDS:raise ValueError(f"第{index}行量程应为low/middle/high")
  seen.add(ident);values={}
  for key in ["x","y"]:
   try:value=float(row.get(key))
   except Exception:raise ValueError(f"第{index}行{key}需要有效数值")
   if not math.isfinite(value) or abs(value)>MAX_ABS:raise ValueError(f"第{index}行{key}必须有限且绝对值不超过1e9")
   values[key]=value
  result.append({"pair_id":ident,"range_label":band,**values})
 return result


def _open(stream):
 """Wrap a binary stream as incremental UTF-8; never load the whole file."""
 if isinstance(stream,str):return io.StringIO(stream),False
 if isinstance(stream,(bytes,bytearray)):return io.StringIO(bytes(stream).decode("utf-8-sig")),False
 return io.TextIOWrapper(stream,encoding="utf-8-sig",newline=""),True


def check_header(fieldnames):
 required={"pair_id","range_label","x","y"}
 if not fieldnames or not required.issubset(set(fieldnames)):
  raise ValueError("CSV需包含pair_id,range_label,x,y列")


def rows_from(stream):
 """Yield validated Reading objects from a text/binary stream of CSV rows.

 Exceptions (including RowError with its source line) surface lazily as the
 caller iterates, so an import can discard the whole batch on the first bad row.
 """
 source,wrap=_open(stream)
 reader=csv.reader(source)
 header_next=next(reader,None)
 header=[str(name).strip() for name in header_next] if header_next else []
 check_header(header)
 columns=tuple(header.index(name) for name in ("pair_id","range_label","x","y"))
 for row in reader:
  line=reader.line_num
  if not row or not any(cell.strip() for cell in row):continue
  if len(row)<len(header):row=row+[""]*(len(header)-len(row))
  elif len(row)>len(header):
   extra=row[len(header):]
   if any(cell.strip() for cell in extra):raise RowError(line,f"列数为{len(row)}，与表头{len(header)}列不一致")
   row=row[:len(header)]
  ident=row[columns[0]].strip();band=row[columns[1]].strip()
  if not ident or len(ident)>MAX_PAIR_ID:raise RowError(line,"配对ID为空或过长")
  if band not in BANDS:raise RowError(line,"量程应为low/middle/high")
  values=[]
  for key,column in (("x",columns[2]),("y",columns[3])):
   try:value=float(row[column])
   except Exception:raise RowError(line,f"{key}需要有效数值")
   if not math.isfinite(value) or abs(value)>MAX_ABS:raise RowError(line,f"{key}必须有限且绝对值不超过1e9")
   values.append(value)
  yield Reading(ident,band,values[0],values[1],line)
 if wrap:source.detach()


def validate_pairs(pairs):
 if len(pairs)<4:raise ValueError("至少需要4组成对读数")
 x=[r["x"] for r in pairs];y=[r["y"] for r in pairs]
 if not all(math.isfinite(v) for v in x+y):raise ValueError("读数必须有限")
 return x,y
