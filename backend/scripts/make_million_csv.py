"""Generate a deterministic million-row acceptance CSV.

The values mimic one field day: three range bands, X/Y both carrying noise
(SD 0.2 / 0.3, so the study lambda=2.25 is the right input), a slow gain/offset
trend, and four deliberate outliers per 250k rows. The last row is normal; the
bad-row / duplicate fixtures are derived from it by the test suite.
"""
import argparse
import random


def generate(path,rows=1_000_000,seed=20261112):
 rng=random.Random(seed);bands=("low","middle","high")
 with open(path,"w",newline="",encoding="utf-8") as handle:
  handle.write("pair_id,range_label,x,y\r\n")
  buffer=[]
  for i in range(rows):
   base=20+(i%1000)/999*80
   x=base+rng.gauss(0,.2);y=1.025*base+.4+rng.gauss(0,.3)
   if i%250_000==249_999:y+=2.8
   buffer.append(f"JQ-{i+1:07d},{bands[min(i*3//rows,2)]},{x:.6f},{y:.6f}\r\n")
   if len(buffer)>=10_000:
    handle.write("".join(buffer));buffer=[]
  if buffer:handle.write("".join(buffer))
 return path


def main():
 parser=argparse.ArgumentParser()
 parser.add_argument("path")
 parser.add_argument("--rows",type=int,default=1_000_000)
 parser.add_argument("--seed",type=int,default=20261112)
 args=parser.parse_args()
 print(generate(args.path,args.rows,args.seed))


if __name__=="__main__":main()
