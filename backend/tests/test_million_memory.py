"""Opt-in acceptance checks for the million-row peaks.

These run the real streaming import, calibration and paging code in-process and
read peak RSS from getrusage, so they are skipped unless PROBE_ACCEPTANCE=1 and
a generated CSV is supplied (see scripts/make_million_csv.py and
scripts/measure_peak.py). The default suite stays fast.
"""
import json,os,subprocess,sys
from pathlib import Path
import pytest

BACKEND=Path(__file__).resolve().parents[1]
CSV=os.environ.get("PROBE_ACCEPTANCE_CSV")
LIMIT_MIB=256


@pytest.fixture(scope="module")
def million_csv(tmp_path_factory):
 if os.environ.get("PROBE_ACCEPTANCE")!="1":pytest.skip("set PROBE_ACCEPTANCE=1 and PROBE_ACCEPTANCE_CSV")
 path=Path(CSV) if CSV else tmp_path_factory.mktemp("million")/"pairs_1m.csv"
 if not path.exists():
  subprocess.run([sys.executable,str(BACKEND/"scripts/make_million_csv.py"),str(path)],check=True)
 return path


def _run(stage,db_path,csv_path,extra=()):
 env=dict(os.environ,DATABASE_URL=f"sqlite:///{db_path}",SEED_DEMO="false",
          PYTHONPATH=f"{BACKEND}:{os.environ.get('PYTHONPATH','')}")
 command=[sys.executable,"-m","scripts.measure_peak",stage,*extra]
 result=subprocess.run(command,cwd=BACKEND,env=env,capture_output=True,text=True,timeout=3600)
 assert result.returncode==0,result.stderr[-2000:]
 return json.loads(result.stdout.strip().splitlines()[-1])


def test_million_row_import_and_compute_stay_under_256_mib(million_csv,tmp_path):
 db_path=tmp_path/"million.db"
 imported=_run("import",db_path,million_csv,("--csv",str(million_csv),"--name","million-row batch"))
 assert imported["pair_count"]==1_000_000 and imported["status"]=="ready"
 assert imported["peak_mib"]<LIMIT_MIB,imported
 computed=_run("compute",db_path,million_csv,("--name","million-row batch"))
 assert computed["status"]=="completed" and computed["n"]==1_000_000
 assert computed["points"]==1_000_000 and computed["sample_size"]<=600
 assert computed["peak_mib"]<LIMIT_MIB,computed
 paged=_run("sample-check",db_path,million_csv,("--name","million-row batch"))
 assert paged["paged_rows"]==paged["stored_rows"]==paged["distinct_pair_ids"]==1_000_000
 assert paged["strictly_ascending"] is True
 archived=_run("archive",db_path,million_csv,("--name","million-row batch"))
 assert archived["points_in_report"]==1_000_000
 exported=_run("export",db_path,million_csv,("--report-id",archived["report_id"],"--out",str(tmp_path/"archive.csv")))
 assert exported["lines"]==1_000_001
 assert exported["peak_mib"]<LIMIT_MIB,exported
