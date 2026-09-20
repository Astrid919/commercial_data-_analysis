"""Purged temporal validation of continuous 6m share change and share-winner ranking."""
from common import *
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression, ElasticNet, Ridge
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor, HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import average_precision_score, roc_auc_score, brier_score_loss, ndcg_score
from sklearn.dummy import DummyClassifier, DummyRegressor
import joblib

def converged(pipeline):
    est=pipeline[-1]
    return bool(np.max(np.atleast_1d(est.n_iter_))<est.max_iter) if isinstance(est,(LogisticRegression,ElasticNet)) else True

def features():
    m,y=load();inn=aggregate(m,y,'INN_key');known=[i for i in inn.index if not i.startswith('UNKNOWN_SKU_')];v=inn.loc[known].to_numpy()
    mapping=pd.read_parquet(PROC/'inn_market_mapping.parquet').set_index('INN')
    a3=aggregate(m,y,'ATC3');a4=aggregate(m,y,'ATC4')
    first=np.where((y>0).any(1),(y>0).argmax(1),60)
    groups={k:g for k,g in m[m.known_inn].groupby('INN')}
    rows=[]
    for t in range(12,60):
        active=m[m.known_inn & (first<=t)]
        counts={lev:active.groupby(lev).INN.nunique() for lev in ['ATC3','ATC4']}
        for i,name in enumerate(known):
            hist=v[i,:t+1];mp=mapping.loc[name];level=mp.market_level;key=mp.market
            if level=='Excluded': continue
            if counts[level].get(key,0)<3:
                a=groups[name].ATC3.unique()
                if len(a)==1 and counts['ATC3'].get(a[0],0)>=3:level,key='ATC3',a[0]
                else:continue
            market=(a4 if level=='ATC4' else a3).loc[key].to_numpy()
            if hist.sum()<=0 or market[t]<=0:continue
            g=groups[name];g=g[first[g.index]<=t]
            share=divide(hist,market[:t+1]);recent=hist[-12:];p=hist>0
            r=dict(INN=name,anchor=MONTHS[t],t=t,market_level=level,market=key,sales_1m=hist[-1],sales_3m=hist[-3:].sum(),sales_6m=hist[-6:].sum(),sales_12m=recent.sum(),peer_share=share[-1],
                volatility=divide(recent.std(),recent.mean()),zero_rate=(recent==0).mean(),ADI=divide(len(recent),(recent>0).sum()),
                months_since_first_sale=t-int(p.argmax()),trailing_zero_rate=float((recent[-3:]==0).mean()),recent_zero_gap=int(hist[-1]==0),
                sku_count=len(g),brand_count=g.Brand.nunique(),strength_count=g.strength_mg.nunique(),form_count=g.dosage_form.nunique(),pack_breadth=g.pack_size.nunique(),
                seasonality=np.corrcoef(hist[12:],hist[:-12])[0,1] if t>=24 and hist[12:].std()>0 and hist[:-12].std()>0 else np.nan,
                CAGR=divide(hist[-12:].sum(),hist[:12].sum())**(12/max(t-11,12))-1)
            for n in [3,6,12]:
                r[f'share_change_{n}m']=share[-1]-share[-n-1]
                r[f'growth_{n}m']=growth(hist[-n:].sum(),hist[-2*n:-n].sum()) if len(hist)>=2*n else np.nan
                r[f'market_growth_{n}m']=growth(market[t-n+1:t+1].sum(),market[t-2*n+1:t-n+1].sum()) if t+1>=2*n else np.nan
            r['relative_growth']=r['growth_6m']-r['market_growth_6m']
            r['future_share_change']=float(divide(v[i,t+6],market[t+6])-share[-1]) if t+6<60 else np.nan
            rows.append(r)
        if t%12==11:print('Opportunity anchors through',MONTHS[t],flush=True)
    df=pd.DataFrame(rows);df['winner']=np.nan
    for t,g in df[df.future_share_change.notna()].groupby('t'):
        # Deterministic tie break by INN; exactly ceil(25%) candidates maximum.
        ix=g.sort_values(['future_share_change','INN'],ascending=[False,True]).head(int(np.ceil(.25*len(g)))).index
        df.loc[g.index,'winner']=0;df.loc[ix[df.loc[ix,'future_share_change']>0],'winner']=1
    df.to_parquet(PROC/'opportunity_panel.parquet',index=False)
    return df

def rank_metrics(g,p):
    y=g.winner.to_numpy();out={'PR_AUC':average_precision_score(y,p),'ROC_AUC':roc_auc_score(y,p),'Brier':brier_score_loss(y,p),'base_rate':y.mean()}
    vals=[]
    for t,h in g.assign(pred=p).groupby('t'):
        h=h.sort_values(['pred','INN'],ascending=[False,True]);d={'anchor':h.anchor.iloc[0],'base_rate':h.winner.mean()}
        for q in [.1,.2]:
            prec=h.head(int(np.ceil(q*len(h)))).winner.mean();d[f'Precision@{int(q*100)}']=prec;d[f'Lift@{int(q*100)}']=prec/h.winner.mean()
        d['NDCG@20']=ndcg_score(h.winner.to_numpy()[None,:],h.pred.to_numpy()[None,:],k=int(np.ceil(.2*len(h))))
        vals.append(d)
    detail=pd.DataFrame(vals)
    out.update({c:detail[c].mean() for c in detail if c not in ['anchor','base_rate']})
    out['n_observations']=len(g);return out,detail

def main():
    df=pd.read_parquet(PROC/'opportunity_panel.parquet') if os.environ.get('REUSE_OPPORTUNITY_PANEL')=='1' and (PROC/'opportunity_panel.parquet').exists() else features()
    exclude=['INN','anchor','t','market_level','market','future_share_change','winner']
    names=[c for c in df if c not in exclude];X=df[names].replace([np.inf,-np.inf],np.nan).copy()
    for c in ['sales_1m','sales_3m','sales_6m','sales_12m']:X[c]=np.log1p(X[c])
    def prep(est):return make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True),StandardScaler(),est)
    classifiers={'Base rate':prep(DummyClassifier(strategy='prior')),'Logistic L2':prep(LogisticRegression(C=.3,max_iter=800)),
       'Elastic Net':prep(LogisticRegression(penalty='elasticnet',solver='saga',l1_ratio=.5,C=.1,max_iter=1500,random_state=SEED)),
       'Random Forest':prep(RandomForestClassifier(n_estimators=120,max_depth=8,min_samples_leaf=30,n_jobs=1,random_state=SEED)),
       'Gradient Boosting':prep(HistGradientBoostingClassifier(max_iter=100,max_leaf_nodes=15,l2_regularization=10,early_stopping=False,random_state=SEED))}
    regressors={'Zero change':prep(DummyRegressor(strategy='constant',constant=0)),'Ridge':prep(Ridge(alpha=100)),
       'Elastic Net':prep(ElasticNet(alpha=.0001,l1_ratio=.5,max_iter=3000)),
       'Random Forest':prep(RandomForestRegressor(n_estimators=100,max_depth=9,min_samples_leaf=30,n_jobs=1,random_state=SEED)),
       'Gradient Boosting':prep(HistGradientBoostingRegressor(max_iter=100,max_leaf_nodes=15,l2_regularization=10,early_stopping=False,random_state=SEED))}
    # Anchor train <=2020-12 => labels <=2021-06; validation anchors >=2021-07.
    train=(df.t<=23)&df.winner.notna();val=df.t.between(30,35)&df.winner.notna();test=df.t.between(48,53)&df.winner.notna()
    refit=(df.t<=41)&df.winner.notna() # all labels available by 2022-12
    rows=[];details=[];regrows=[];preds={}
    for name,model in classifiers.items():
        model.fit(X[train],df.loc[train,'winner']);p=model.predict_proba(X[val])[:,1];sc,detail=rank_metrics(df[val],p)
        rows.append(dict(model=name,split='validation_2021H2',converged=converged(model),**sc));details.append(detail.assign(model=name,split='validation'))
    best=max([r for r in rows if r['converged']],key=lambda r:(r['Lift@20'],r['PR_AUC']))['model']
    for name,model in regressors.items():
        model.fit(X[train],df.loc[train,'future_share_change']);p=model.predict(X[val]);e=p-df.loc[val,'future_share_change']
        regrows.append(dict(model=name,split='validation_2021H2',converged=converged(model),MAE=np.abs(e).mean(),RMSE=np.sqrt((e**2).mean())))
    bestr=min([r for r in regrows if r['converged']],key=lambda r:r['MAE'])['model']
    jsave({'classifier':best,'regressor':bestr,'selection':'classifier mean anchor Lift@20; regression MAE','train_anchor_end':'2020-12','train_label_end':'2021-06','validation_anchors':'2021-07 to 2021-12','test_anchors':'2023-01 to 2023-06','test_refit_label_end':'2022-12','feature_columns':names},OUT/'models/opportunity_lock.json')
    for name,model in classifiers.items():
        model.fit(X[refit],df.loc[refit,'winner']);p=model.predict_proba(X[test])[:,1];sc,detail=rank_metrics(df[test],p)
        rows.append(dict(model=name,split='locked_test_2023H1',converged=converged(model),**sc));details.append(detail.assign(model=name,split='test'))
        if name==best:
            preds['probability']=p
            bins=pd.DataFrame({'p':p,'actual':df.loc[test,'winner'].values});bins['bin']=pd.cut(bins.p,np.linspace(0,1,11),include_lowest=True)
            save(bins.groupby('bin',observed=True).agg(mean_probability=('p','mean'),actual_rate=('actual','mean'),count=('p','size')).reset_index(),'opportunity_calibration')
    for name,model in regressors.items():
        model.fit(X[refit],df.loc[refit,'future_share_change']);p=model.predict(X[test]);e=p-df.loc[test,'future_share_change']
        regrows.append(dict(model=name,split='locked_test_2023H1',converged=converged(model),MAE=np.abs(e).mean(),RMSE=np.sqrt((e**2).mean())))
    save(pd.DataFrame(rows),'opportunity_model_metrics');save(pd.concat(details),'opportunity_anchor_metrics');save(pd.DataFrame(regrows),'opportunity_regression_metrics')
    save(df.loc[test,['INN','anchor','winner','future_share_change']].assign(predicted_probability=preds['probability']),'opportunity_holdout_predictions')
    alltrain=df.winner.notna();future=df.t.eq(59)
    cl=classifiers[best].fit(X[alltrain],df.loc[alltrain,'winner']);re=regressors[bestr].fit(X[alltrain],df.loc[alltrain,'future_share_change'])
    future_result=df.loc[future,['INN','market_level','market','peer_share']].copy();future_result['opportunity_probability']=cl.predict_proba(X[future])[:,1];future_result['predicted_share_change_6m']=re.predict(X[future]);save(future_result,'opportunity_2024')
    joblib.dump({'classifier':cl,'regressor':re,'features':names},OUT/'models/opportunity_final.joblib')
    # Temporal block uncertainty: resample anchor months, not dependent INN/month rows.
    a=pd.concat(details);a=a[(a.model==best)&a.split.eq('test')]['Lift@20'].to_numpy();rng=np.random.default_rng(SEED)
    boot=rng.choice(a,size=(2000,len(a)),replace=True).mean(1)
    jsave({'test_lift20_mean':a.mean(),'anchor_bootstrap_95_low':np.quantile(boot,.025),'anchor_bootstrap_95_high':np.quantile(boot,.975),'anchors':len(a),'caution':'Six overlapping outcome months: descriptive interval; not independent replication'},OUT/'qa/opportunity_uncertainty.json')
if __name__=='__main__':main()
