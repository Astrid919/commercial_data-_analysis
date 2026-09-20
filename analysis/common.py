"""Shared configuration, IO and metrics for the full portfolio study."""
from pathlib import Path
import json, hashlib, os, sys
os.environ.setdefault('OMP_NUM_THREADS','1')
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
_local = Path(__file__).resolve().parents[2] / '.runtime'
if _local.exists(): sys.path.insert(0, str(_local))
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'outputs/qa/matplotlib_cache'))
SOURCE = ROOT.parent / 'data' / 'teva_sales.csv'
OUT = ROOT / 'outputs'
TABLE = OUT / 'tables'
PROC = ROOT / 'data' / 'processed'
SEED = 20260920
MONTHS = pd.date_range('2019-01-01', periods=60, freq='MS')
for p in [TABLE, PROC, OUT/'figures', OUT/'models', OUT/'qa', ROOT/'report']:
    p.mkdir(parents=True, exist_ok=True)

def save(df, name):
    df.to_csv(TABLE / (name+'.csv'), index=False, encoding='utf-8-sig')

def jsave(obj, path):
    def default(v):
        if isinstance(v, np.generic): return v.item()
        if isinstance(v, (Path, pd.Timestamp)): return str(v)
        if isinstance(v, np.ndarray): return v.tolist()
        raise TypeError(type(v).__name__)
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=default), encoding='utf-8')

def load():
    return pd.read_parquet(PROC/'sku_attributes.parquet'), np.load(PROC/'sales.npy')

def aggregate(meta, values, key):
    return pd.DataFrame(values).groupby(meta[key].to_numpy(), sort=True).sum()

def divide(a,b):
    result=np.divide(a,b,out=np.full(np.broadcast_shapes(np.shape(a),np.shape(b)),np.nan),where=np.asarray(b)!=0)
    return result.item() if np.ndim(result)==0 else result

def growth(a,b): return divide(a,b)-1

def metrics(y, p, train):
    scale=np.mean(np.abs(train[:,12:]-train[:,:-12]),axis=1)
    valid=scale>1e-9
    return dict(WAPE=float(np.abs(y-p).sum()/max(y.sum(),1e-9)),
                Bias=float((p-y).sum()/max(y.sum(),1e-9)),
                RMSE=float(np.sqrt(np.mean((y-p)**2))),
                MASE=float(np.mean(np.abs(y[valid]-p[valid])/scale[valid,None])) if valid.any() else np.nan,
                MASE_eligible=int(valid.sum()), observations=int(y.size))

def patterns(y):
    n,t=y.shape; positive=y>0
    nz=positive.sum(1); anypos=nz>0
    leading=np.where(anypos, positive.argmax(1), t)
    trailing=np.where(anypos, positive[:,::-1].argmax(1), t)
    internal=(y==0).sum(1)-leading-trailing
    internal=np.where(anypos,np.maximum(internal,0),0)
    mean=y.mean(1); cv=divide(y.std(1),mean)
    posmean=divide(y.sum(1),nz)
    posvar=divide(((y-posmean[:,None])**2*positive).sum(1),nz)
    cv2=divide(posvar,posmean**2)
    adi=divide(t,nz)
    ac=[]; ss=[]; ts=[]
    # Additive decomposition proxy on log sales. Explicitly not STL.
    x=np.arange(t); design=np.column_stack([np.ones(t), x, pd.get_dummies(x%12,drop_first=True).to_numpy()]).astype(float)
    z=np.log1p(y); coef=np.linalg.lstsq(design,z.T,rcond=None)[0]
    resid=z.T-design@coef
    seasonal=design[:,2:]@coef[2:]; trend=design[:,1:2]@coef[1:2]
    rv=resid.var(0)
    ss=np.clip(1-divide(rv,(resid+seasonal).var(0)),0,1)
    ts=np.clip(1-divide(rv,(resid+trend).var(0)),0,1)
    for row in y:
        ac.append(np.corrcoef(row[12:],row[:-12])[0,1] if t>24 and np.std(row[12:])>0 and np.std(row[:-12])>0 else np.nan)
    seg=np.select([~anypos,trailing>=6,leading>=t-12,adi>=1.32,ss>=.5,cv>=1],
                  ['No observed demand','Potential discontinued','Launch / lifecycle','Intermittent','Seasonal','Lumpy / volatile'],default='Stable')
    seg=np.where((adi>=1.32)&(cv2>=.49)&(trailing<6)&(leading<t-12),'Lumpy / volatile',seg)
    return pd.DataFrame(dict(zero_rate=(y==0).mean(1),mean_demand=mean,CV=cv,ADI=adi,CV2_positive=cv2,
        leading_zeros=leading,trailing_zeros=trailing,internal_zero_months=internal,
        seasonality_strength=ss,trend_strength=ts,lag12_autocorrelation=ac,segment=seg))
