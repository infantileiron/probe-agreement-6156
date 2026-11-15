"""Chunked accumulation of the calibration statistics.

Only small per-chunk sums survive between chunks, so peak memory does not grow
with pair count. Chunks are centred on their own local means and re-centred on
the global moments with the parallel-axis identity; this keeps precision when
x/y approach the +/-1e9 limit. ``deming.regress``/``agreement.analyze`` remain
the single-pass reference for small samples.
"""
import math

OUTLIER_SAMPLE=200
EVEN_SAMPLE=400


def safe_sqrt(value):
 return math.sqrt(value) if value>0 else 0.


class MomentPass:
 """First pass: count and means of x and y."""
 def __init__(self):
  self.n=0;self.parts_x=[];self.parts_y=[]

 def add(self,readings):
  self.n+=len(readings)
  self.parts_x.append(math.fsum(r.x for r in readings))
  self.parts_y.append(math.fsum(r.y for r in readings))

 def finish(self):
  if self.n<4:raise ValueError("Deming至少需要4组完整配对")
  return self.n,math.fsum(self.parts_x)/self.n,math.fsum(self.parts_y)/self.n


class MomentPass2:
 """Second pass: centred second moments plus BA/regression sums."""
 def __init__(self,mx,my):
  self.mx=mx;self.my=my;self.mm=(mx+my)/2;self.bias=my-mx;self.n=0
  self.vx=[];self.vy=[];self.cov=[];self.total_ss=[];self.ss_m=[];self.cov_md=[]

 def add(self,readings):
  """Accumulate one chunk.

  Values are first shifted by the global means (subtracting nearby doubles is
  exact, Sterbenz), so chunk means, squares and cross terms stay small even
  when readings sit near +/-1e9 with a narrow spread.
  """
  mx,my,mm,bias=self.mx,self.my,self.mm,self.bias
  n=len(readings);self.n+=n
  dx=[r.x-mx for r in readings];dy=[r.y-my for r in readings]
  diffs=[r.y-r.x for r in readings];means=[(a+b)/2 for a,b in zip(dx,dy)]
  cdx=math.fsum(dx)/n;cdy=math.fsum(dy)/n;cdm=math.fsum(means)/n;cdb=math.fsum(diffs)/n
  vx=math.fsum((v-cdx)**2 for v in dx)+n*cdx*cdx
  vy=math.fsum((v-cdy)**2 for v in dy)+n*cdy*cdy
  cov=math.fsum((a-cdx)*(b-cdy) for a,b in zip(dx,dy))+n*cdx*cdy
  # means are already relative to the global centre (mm is 0 in shifted space),
  # so the parallel-axis term re-centres on the chunk's own mean relative to 0;
  # differences keep their original scale and re-centre on the global bias.
  td=math.fsum((d-cdb)**2 for d in diffs)+n*(cdb-bias)**2
  sm=math.fsum((m-cdm)**2 for m in means)+n*cdm*cdm
  cmd=math.fsum((m-cdm)*(d-cdb) for m,d in zip(means,diffs))+n*cdm*(cdb-bias)
  self.vx.append(vx);self.vy.append(vy);self.cov.append(cov)
  self.total_ss.append(td);self.ss_m.append(sm);self.cov_md.append(cmd)

 def finish(self):
  n=self.n
  return {"n":n,"vx":math.fsum(self.vx)/(n-1),"vy":math.fsum(self.vy)/(n-1),"cov":math.fsum(self.cov)/(n-1),
          "total_ss":math.fsum(self.total_ss),"ss_m":math.fsum(self.ss_m),"cov_md":math.fsum(self.cov_md)}


def proportional_from_moments(bias,mean_mean,total_ss,ss,cov_md):
 """OLS of d on m from moments; the SSE uses the centred-sum identity."""
 if ss==0:return {"estimable":False,"slope":None,"intercept":None,"r_squared":None,"reason":"两探头均值读数为常量，比例偏倚回归不可估计"}
 slope=cov_md/ss;intercept=bias-slope*mean_mean
 residual_sse=max(0.,total_ss-2*slope*cov_md+slope*slope*ss)
 return {"estimable":True,"slope":slope,"intercept":intercept,"r_squared":None if total_ss==0 else max(0.,min(1.,1-residual_sse/total_ss)),"reason":""}


class DetailPass:
 """Third pass: per-pair markings plus the bounded chart sample.

 Counts are taken over every reading; the sample only feeds charts and is
 always reported with its actual size next to the full n.
 """
 def __init__(self,n,slope,intercept,bias,low,high,tolerance,proportional=None):
  self.n=n;self.slope=slope;self.intercept=intercept;self.bias=bias
  self.low=low;self.high=high;self.tolerance=tolerance
  self.proportional=proportional if proportional and proportional.get("estimable") else None
  self.proportional_ss=[]
  self.outside_loa=0;self.outside_tolerance=0
  self.residual_ss=[]
  self.sample=[];self.first_outliers=[]
  step=max(1,n//EVEN_SAMPLE);self.step=step;self.next_sample=0;self.index=0

 def add(self,readings):
  slope,intercept,low,high,tolerance=self.slope,self.intercept,self.low,self.high,self.tolerance
  rows=[];residual_ss=[];prop_ss=[];prop=self.proportional
  for r in readings:
   diff=r.y-r.x;fitted=intercept+slope*r.x;residual=r.y-fitted
   outside=diff<low or diff>high;outside_tol=abs(diff)>tolerance
   if outside:self.outside_loa+=1
   if outside_tol:self.outside_tolerance+=1
   residual_ss.append(residual*residual)
   if prop:prop_ss.append((diff-prop["intercept"]-prop["slope"]*((r.x+r.y)/2))**2)
   rows.append({"pair_id":r.pair_id,"range_label":r.range_label,"x":r.x,"y":r.y,"mean":(r.x+r.y)/2,"difference":diff,"fitted_y":fitted,"residual_y":residual,"outside_loa":outside,"outside_tolerance":outside_tol})
   if self.index>=self.next_sample and len(self.sample)<EVEN_SAMPLE:
    self.sample.append(rows[-1]);self.next_sample+=self.step
   if outside and len(self.first_outliers)<OUTLIER_SAMPLE:self.first_outliers.append(rows[-1])
   self.index+=1
  self.residual_ss.append(math.fsum(residual_ss))
  if prop:self.proportional_ss.append(math.fsum(prop_ss))
  return rows

 def finalize_sample(self):
  """Add the first flagged pairs so charts still show them when sampled."""
  outliers=self.first_outliers;existing={row["pair_id"] for row in self.sample}
  for row in outliers:
   if len(self.sample)>=(EVEN_SAMPLE+OUTLIER_SAMPLE):break
   if row["pair_id"] in existing:continue
   self.sample.append(row);existing.add(row["pair_id"])
  return self.sample

 def rmse(self):
  return safe_sqrt(math.fsum(self.residual_ss)/self.n) if self.n else 0.

 def proportional_sse(self):
  """Direct residual sum of squares for d = alpha + beta*m (matches reference)."""
  return math.fsum(self.proportional_ss) if self.proportional_ss else None
