"""Run stages in independent processes; results and model locks are persisted."""
from pathlib import Path
import os, sys, subprocess, argparse, time
ROOT=Path(__file__).resolve().parent
os.environ.setdefault('PYTHONIOENCODING','utf-8')
os.environ['OMP_NUM_THREADS']='1'
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['MKL_NUM_THREADS']='1'
local=ROOT.parent/'.runtime'
if local.exists(): os.environ['PYTHONPATH']=str(local)+os.pathsep+os.environ.get('PYTHONPATH','')
p=argparse.ArgumentParser();p.add_argument('--from-stage',type=int,default=1);p.add_argument('--to-stage',type=int,default=13);a=p.parse_args()
for file in sorted((ROOT/'analysis').glob('[0-9][0-9]_*.py')):
    if a.from_stage<=int(file.name[:2])<=a.to_stage:
        print('\nRUN '+file.name,flush=True); start=time.time()
        subprocess.run([sys.executable,str(file)],check=True,cwd=ROOT)
        print(f'DONE {time.time()-start:.1f}s',flush=True)
