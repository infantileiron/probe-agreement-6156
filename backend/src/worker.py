import logging,time
from pathlib import Path
from .config.database import Session,initialize
from .utils.queue import client,QUEUE
from .services.run_service import compute
heartbeat=Path("/artifacts/worker-heartbeat")
# One worker process handles one run at a time. Calibration streams the dataset
# in bounded passes, so a million-pair run stays inside the process memory
# budget instead of holding the JSON payload in RAM.
initialize()
while True:
 try:
  heartbeat.parent.mkdir(parents=True,exist_ok=True);heartbeat.touch()
  item=client().blpop(QUEUE,timeout=2)
  if item:
   with Session() as db:compute(db,item[1])
 except Exception:logging.exception("Worker error");time.sleep(2)
