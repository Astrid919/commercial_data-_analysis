"""Origin-safe recursive models and vectorized intermittent-demand methods."""
from common import *
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer

def intermittent(y,h,alpha=.1):
    n,t=y.shape; first=np.where((y>0).any(1),(y>0).argmax(1),t)
    z=np.zeros(n);q=np.ones(n);prob=np.zeros(n);gap=np.ones(n)
    for j in range(t):
        new=first==j;active=first<=j;hit=y[:,j]>0
        z[new]=y[new,j];q[new]=j+1;prob[new]=1/(j+1)
        old=active&~new
        prob[old]=(1-alpha)*prob[old]+alpha*hit[old]
        update=old&hit;z[update]=(1-alpha)*z[update]+alpha*y[update,j];q[update]=(1-alpha)*q[update]+alpha*gap[update]
        gap[hit]=1;gap[~hit]+=1
    return {k:np.repeat(v[:,None],h,1) for k,v in {'Croston':z/q,'SBA':(1-alpha/2)*z/q,'TSB':z*prob}.items()}

def damped_ets(y,h):
    """ETS(A,Ad,N) on additive seasonally adjusted series; finite grid SSE fit."""
    n,t=y.shape;trend=np.arange(t)
    detrend=y-(y@ (trend-trend.mean()) / ((trend-trend.mean())**2).sum())[:,None]*(trend-trend.mean())
    seas=np.column_stack([detrend[:,j::12].mean(1) for j in range(12)]);seas-=seas.mean(1,keepdims=True)
    z=y-seas[:,np.arange(t)%12]
    best=np.full(n,np.inf);pred=np.zeros((n,h))
    for alpha in [.2,.5,.8]:
        for beta in [.05,.2]:
            for phi in [.8,.95]:
                l=z[:,0].copy();b=np.zeros(n);sse=np.zeros(n)
                for j in range(1,t):
                    err=z[:,j]-(l+phi*b);sse+=err**2
                    old=l.copy();l=alpha*z[:,j]+(1-alpha)*(l+phi*b);b=beta*(l-old)+(1-beta)*phi*b
                p=l[:,None]+b[:,None]*np.cumsum(phi**np.arange(1,h+1))[None,:]+seas[:,np.arange(t,t+h)%12]
                ix=sse<best;pred[ix]=p[ix];best[ix]=sse[ix]
    return np.maximum(pred,0)

def lag_features(y,t,static):
    a=y[:,:t];scale=np.maximum(a[:,-12:].mean(1),1)
    cols=[a[:,-k]/scale for k in [1,2,3,6,12]]
    cols += [a[:,-k:].mean(1)/scale for k in [3,6,12]]
    cols += [a[:,-k:].std(1)/scale for k in [6,12]]
    cols += [np.log1p(scale),(a[:,-12:]==0).mean(1),12/np.maximum((a[:,-12:]>0).sum(1),1),np.full(len(a),np.sin(2*np.pi*t/12)),np.full(len(a),np.cos(2*np.pi*t/12))]
    return np.nan_to_num(np.column_stack(cols+[static]),nan=-1,posinf=10,neginf=-10),scale

def all_forecasts(y,h,static):
    t=y.shape[1]
    out={'Seasonal Naive':np.tile(y[:,-12:],(1,int(np.ceil(h/12))))[:,:h], 'Damped ETS':damped_ets(y,h)}
    xx=[];yy=[]
    for j in range(12,t):
        x,s=lag_features(y,j,static);xx.append(x);yy.append(np.clip(y[:,j]/s,0,25))
    X=np.vstack(xx);Y=np.concatenate(yy)
    categorical=list(range(X.shape[1]-4,X.shape[1]));numeric=list(range(X.shape[1]-4))
    prep=ColumnTransformer([('numeric',StandardScaler(),numeric),('category',OneHotEncoder(handle_unknown='ignore'),categorical)])
    models={'Ridge ARX':make_pipeline(prep,Ridge(alpha=100,solver='lsqr')),
            'Global Gradient Boosting':HistGradientBoostingRegressor(max_iter=85,max_leaf_nodes=23,l2_regularization=20,categorical_features=categorical,early_stopping=False,random_state=SEED)}
    for name,model in models.items():
        model.fit(X,Y);ext=y.copy();p=[]
        for j in range(h):
            x,s=lag_features(ext,t+j,static);forecast=np.clip(model.predict(x),0,25)*s
            p.append(forecast);ext=np.column_stack([ext,forecast])
        out[name]=np.column_stack(p)
    return out,models

def static_inn(m,keys,cutoff,y):
    # Only SKU characteristics observed through the forecast origin.
    active=(y[:,:cutoff]>0).any(1);g=m[active].groupby('INN_key')
    a=g.agg(sku_count=('SKU','size'),pack=('pack_size','median'),strength=('strength_mg','median'),forms=('dosage_form','nunique'))
    a=a.reindex(keys).fillna(0)
    # High-cardinality identity levels are pooled by origin-known volume only.
    # 254 retained levels + Other meet HistGB's 255-category limit.
    observed=m[active].copy();observed['origin_sales']=y[active,:cutoff].sum(1)
    codes=[]
    for field in ['INN_key','ATC3','ATC4','dosage_form']:
        ranks=observed.groupby(field).origin_sales.sum().sort_values(ascending=False)
        levels=list(ranks.head(254).index);mapping={v:i for i,v in enumerate(levels)}
        if field=='INN_key':values=pd.Series(keys,index=keys)
        else:
            dominant=observed.groupby(['INN_key',field]).origin_sales.sum().reset_index().sort_values('origin_sales',ascending=False).drop_duplicates('INN_key').set_index('INN_key')[field]
            values=dominant.reindex(keys)
        codes.append(values.map(mapping).fillna(len(levels)).to_numpy())
    return np.column_stack([np.log1p(a.to_numpy()),*codes])
