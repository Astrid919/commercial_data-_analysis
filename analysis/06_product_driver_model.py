"""Associational INN/month fixed effects plus a one-step predictive driver model."""
from common import *
import statsmodels.api as sm
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_squared_error
from sklearn.inspection import permutation_importance
from sklearn.preprocessing import OrdinalEncoder
import joblib

def main():
    m,y=load();valid=m.known_inn & m.strength_mg.notna() & m.pack_size.notna()
    a=m[valid].copy();z=np.log1p(y[valid]); forms=pd.get_dummies(a.dosage_form,prefix='form',dtype=float)
    # Reference category chosen explicitly and written to metadata.
    reference='form_Oral solid'
    x=pd.concat([np.log1p(a[['pack_size','strength_mg']]).rename(columns={'pack_size':'log1p_pack_size','strength_mg':'log1p_strength_mg'}),forms.drop(columns=[reference],errors='ignore')],axis=1)
    x=x-x.groupby(a.INN).transform('mean');x=x.loc[:,x.std()>1e-10]
    # Absorb INN x calendar-month fixed effects: compare SKUs within molecule/month.
    zz=z-pd.DataFrame(z,index=a.index).groupby(a.INN).transform('mean').to_numpy()
    zz=zz-zz.mean(0,keepdims=True)
    xx=np.repeat(x.to_numpy(),60,axis=0)
    fit=sm.OLS(zz.ravel(),xx).fit(cov_type='cluster',cov_kwds={'groups':np.repeat(a.SKU.to_numpy(),60)})
    ci=fit.conf_int();save(pd.DataFrame({'term':x.columns,'coefficient':fit.params,'cluster_se_SKU':fit.bse,'p_value':fit.pvalues,'ci95_low':ci[:,0],'ci95_high':ci[:,1]}),'attribute_fixed_effects')
    jsave({'complete_case_skus':len(a),'observations':int(z.size),'inn_count':a.INN.nunique(),'form_reference':reference,'estimator':'OLS with absorbed INN x calendar-month FE; SKU-clustered asymptotic SE; no SKU FE because attributes time invariant','interpretation':'Association, not causation; mg only comparable within molecule and formulation'},OUT/'qa/attribute_model.json')
    # Global one-step model: lag actuals available at each previous month.
    idx=np.flatnonzero(m.known_inn);a=m.iloc[idx]
    enc=OrdinalEncoder(handle_unknown='use_encoded_value',unknown_value=-1)
    cat=enc.fit_transform(a[['INN','ATC4','dosage_form']])
    static=np.column_stack([cat,np.log1p(a.pack_size),np.log1p(a.strength_mg)])
    names=['INN','ATC4','dosage_form','log_pack','log_strength','month_sin','month_cos','log_lag1','log_lag12','log_roll3','log_roll12']
    frames=[];targets=[];times=[]
    for t in range(12,60):
        v=y[idx,:t]
        frames.append(np.column_stack([static,np.full(len(idx),np.sin(2*np.pi*t/12)),np.full(len(idx),np.cos(2*np.pi*t/12)),np.log1p(v[:,-1]),np.log1p(v[:,-12]),np.log1p(v[:,-3:].mean(1)),np.log1p(v[:,-12:].mean(1))]))
        targets.append(np.log1p(y[idx,t]));times.extend([t]*len(idx))
    X=np.nan_to_num(np.vstack(frames),nan=-1);Y=np.concatenate(targets);times=np.array(times)
    train=times<36;val=(times>=36)&(times<48);test=times>=48
    model=HistGradientBoostingRegressor(max_iter=120,max_leaf_nodes=23,l2_regularization=10,random_state=SEED,early_stopping=False).fit(X[train],Y[train])
    rows=[]
    for split,mask in [('validation_2022',val),('holdout_2023',test)]:
        p=np.maximum(np.expm1(model.predict(X[mask])),0);actual=np.expm1(Y[mask]);rows.append(dict(split=split,log_RMSE=np.sqrt(mean_squared_error(Y[mask],model.predict(X[mask]))),WAPE=np.abs(actual-p).sum()/actual.sum(),observations=int(mask.sum())))
    save(pd.DataFrame(rows),'attribute_ml_metrics')
    # Validation only, sampled evenly for computational economy; all data used in training.
    rng=np.random.default_rng(SEED);ix=rng.choice(np.flatnonzero(val),min(12000,val.sum()),replace=False)
    imp=permutation_importance(model,X[ix],Y[ix],n_repeats=3,random_state=SEED,scoring='neg_root_mean_squared_error')
    save(pd.DataFrame({'feature':names,'increase_log_RMSE':imp.importances_mean,'repeat_sd':imp.importances_std}).sort_values('increase_log_RMSE',ascending=False),'attribute_permutation_importance')
    joblib.dump({'model':model,'encoder':enc,'features':names},OUT/'models/attribute_ml.joblib')
if __name__=='__main__': main()
