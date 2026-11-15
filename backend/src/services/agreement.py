import math


def analyze(x,y):
 if len(x)!=len(y) or len(x)<4:raise ValueError("一致性分析至少需要4组配对")
 if not all(math.isfinite(v) for v in x+y):raise ValueError("读数必须有限")
 n=len(x);means=[(a+b)/2 for a,b in zip(x,y)];diffs=[b-a for a,b in zip(x,y)];bias=math.fsum(diffs)/n
 total_ss=math.fsum((d-bias)**2 for d in diffs);sample_sd=math.sqrt(total_ss/(n-1));mm=math.fsum(means)/n
 ss=math.fsum((m-mm)**2 for m in means);cov_md=math.fsum((m-mm)*(d-bias) for m,d in zip(means,diffs))
 low=bias-1.96*sample_sd;high=bias+1.96*sample_sd
 outside=sum(d<low or d>high for d in diffs)
 return agreement_from_moments(n,bias,sample_sd,mm,total_ss,ss,cov_md,outside)


def _proportional(bias,mean_mean,total_ss,ss,cov_md):
 if ss==0:return {"estimable":False,"slope":None,"intercept":None,"r_squared":None,"reason":"两探头均值读数为常量，比例偏倚回归不可估计"}
 slope=cov_md/ss;intercept=bias-slope*mean_mean
 residual_sse=max(0.,total_ss-2*slope*cov_md+slope*slope*ss)
 return {"estimable":True,"slope":slope,"intercept":intercept,"r_squared":None if total_ss==0 else max(0.,min(1.,1-residual_sse/total_ss)),"reason":""}


def agreement_from_moments(n,bias,sample_sd,mean_mean,total_ss,ss,cov_md,outside_loa,proportional=None):
 """Build the Bland-Altman payload from already accumulated moments.

 ``outside_loa`` must be counted over every reading, not over a chart sample.
 The proportional OLS is optional so the streaming path can reuse its own
 second-pass sums (stream_stats.proportional_from_moments).
 """
 if n<4:raise ValueError("一致性分析至少需要4组配对")
 low=bias-1.96*sample_sd;high=bias+1.96*sample_sd
 return {"n":n,"bias":bias,"sample_sd":sample_sd,"loa_low":low,"loa_high":high,"outside_loa":outside_loa,"proportional":proportional or _proportional(bias,mean_mean,total_ss,ss,cov_md),"difference_definition":"y-x","sd_ddof":1,"limits_note":"mean(y-x) ± 1.96 × sample SD；一致性界限不是置信区间，不直接证明设备可互换。"}
