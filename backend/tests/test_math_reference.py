"""Streaming moments must reproduce the original single-pass algorithms."""
import math,random

from src.services.agreement import agreement_from_moments,analyze
from src.services.deming import regress,regress_from_moments
from src.services.stream_stats import DetailPass,MomentPass,MomentPass2,proportional_from_moments


class Row:
 __slots__=("pair_id","range_label","x","y")
 def __init__(self,x,y,pair_id="",range_label="low"):
  self.x=x;self.y=y;self.pair_id=pair_id;self.range_label=range_label


def _stream(readings,chunk):
 for i in range(0,len(readings),chunk):yield readings[i:i+chunk]


def _run(readings,chunk,lam,tolerance):
 first=MomentPass()
 for batch in _stream(readings,chunk):first.add(batch)
 n,mx,my=first.finish()
 second=MomentPass2(mx,my)
 for batch in _stream(readings,chunk):second.add(batch)
 m=second.finish()
 deming=regress_from_moments(n,mx,my,m["vx"],m["vy"],m["cov"],lam)
 total_ss=m["total_ss"];sd=math.sqrt(total_ss/(n-1));bias=my-mx
 prop=proportional_from_moments(bias,second.mm,total_ss,m["ss_m"],m["cov_md"])
 low,high=bias-1.96*sd,bias+1.96*sd
 detail=DetailPass(n,deming["slope"],deming["intercept"],bias,low,high,tolerance,prop)
 for batch in _stream(readings,chunk):detail.add(batch)
 prop["r_squared"]=max(0.,min(1.,1-detail.proportional_sse()/total_ss)) if total_ss else None
 agreement=agreement_from_moments(n,bias,sd,second.mm,total_ss,m["ss_m"],m["cov_md"],detail.outside_loa,proportional=prop)
 deming["residual_rmse_y"]=detail.rmse()
 return deming,agreement


def _seed_points(n,seed=20261112):
 rng=random.Random(seed);xs=[];ys=[]
 for i in range(n):
  base=20+i/max(n-1,1)*80;x=base+rng.gauss(0,.2);y=1.025*base+.4+rng.gauss(0,.3)
  if i%41==17:y+=2.8
  xs.append(x);ys.append(y)
 return xs,ys


def _stream_rmse(xs,ys,chunk):
 deming,_=_run([Row(a,b) for a,b in zip(xs,ys)],chunk,2.25,2.)
 return deming["residual_rmse_y"]


def test_streaming_matches_single_pass_for_small_samples():
 xs,ys=_seed_points(240)
 deming_ref=regress(xs,ys,2.25);agreement_ref=analyze(xs,ys)
 for chunk in (1,7,50,240):
  deming,agreement=_run([Row(a,b) for a,b in zip(xs,ys)],chunk,2.25,2.)
  deming.pop("residual_rmse_y",None)
  for key in ("slope","intercept","x_variance","y_variance","covariance","mean_x","mean_y"):
   assert math.isclose(deming[key],deming_ref[key],rel_tol=1e-12,abs_tol=1e-12),key
  streaming_rmse=_stream_rmse(xs,ys,chunk)
  rmse=math.sqrt(sum((b-(deming_ref["intercept"]+deming_ref["slope"]*a))**2 for a,b in zip(xs,ys))/len(xs))
  assert math.isclose(streaming_rmse,rmse,rel_tol=1e-9,abs_tol=1e-12)
  for key in ("bias","sample_sd","loa_low","loa_high","outside_loa"):
   assert math.isclose(agreement[key],agreement_ref[key],rel_tol=1e-12,abs_tol=1e-12),key
  for key in ("slope","intercept","r_squared"):
   assert math.isclose(agreement["proportional"][key],agreement_ref["proportional"][key],rel_tol=1e-9,abs_tol=1e-12),key


def test_streaming_stays_exact_near_the_value_limit():
 """At +/-1e9 the naive two-pass reference loses the small spread to rounding;
 the chunk-shifted path should match the exact values instead."""
 from fractions import Fraction
 xs=[1e9-5000+i for i in range(40)];ys=[v*.999+3 for v in xs]
 deming,agreement=_run([Row(a,b) for a,b in zip(xs,ys)],7,2.25,2.)
 n=len(xs);fx=[Fraction(v) for v in xs];fy=[Fraction(v) for v in ys]
 mx=sum(fx)/n;my=sum(fy)/n
 vx=sum((v-mx)**2 for v in fx)/(n-1);vy=sum((v-my)**2 for v in fy)/(n-1)
 cov=sum((a-mx)*(b-my) for a,b in zip(fx,fy))/(n-1)
 assert math.isclose(deming["x_variance"],float(vx),rel_tol=1e-12)
 assert math.isclose(deming["y_variance"],float(vy),rel_tol=1e-12)
 assert math.isclose(deming["covariance"],float(cov),rel_tol=1e-12)
 delta=float(vy)-2.25*float(vx);root=math.hypot(delta,2*math.sqrt(2.25)*float(cov))
 expected=(delta+root)/(2*float(cov)) if delta>=0 else 2*2.25*float(cov)/(root-delta)
 assert math.isclose(deming["slope"],expected,rel_tol=1e-10)
 assert agreement["outside_loa"]==0
