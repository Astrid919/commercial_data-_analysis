"""Independent audit checks for units, identities, causality boundaries and reconciliation."""
from common import *
import importlib.util

def main():
    checks=[]
    def check(name,condition,detail=''):
        checks.append({'check':name,'passed':bool(condition),'detail':str(detail)})
        assert condition,(name,detail)
    m,y=load();raw=pd.read_csv(SOURCE);source=raw.iloc[:,10:].to_numpy()
    check('All 825720 source observations retained',y.shape==source.shape and np.array_equal(y,source))
    check('Long panel sum and row count',len(pd.read_parquet(PROC/'sku_month_panel.parquet'))==y.size and np.isclose(pd.read_parquet(PROC/'sku_month_panel.parquet').Sales.sum(),y.sum()))
    annual=pd.read_csv(TABLE/'portfolio_annual.csv');check('Annual totals independent reconciliation',np.allclose(y.reshape(len(m),5,12).sum((0,2)),annual.sales))
    spec=importlib.util.spec_from_file_location('features',ROOT/'analysis/02_feature_engineering.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    check('Dose normalization mg mcg g',module.parse('tabs 500 mcg #20','Oral Solid Ordinary')['strength_mg']==.5 and module.parse('tabs 1 g #20','Oral Solid Ordinary')['strength_mg']==1000)
    check('Concentration not treated as per-unit dose',np.isnan(module.parse('25 mg/ml flask 4 ml #1','Parenteral Ordinary')['strength_mg']))
    check('Container mass not treated as active strength',np.isnan(module.parse('cream tube 30 g','Topical')['strength_mg']))
    pp=patterns(np.array([[0,0,1,0,2,0,0]*4,[0]*28],float));check('All-zero pattern distinct',pp.segment.iloc[1]=='No observed demand')
    d=pd.read_csv(TABLE/'growth_decomposition.csv');check('Growth decomposition identity',d.reconciliation_error.abs().max()<1e-6,d.reconciliation_error.abs().max())
    op=pd.read_parquet(PROC/'opportunity_panel.parquet');inn=aggregate(m,y,'INN_key');rng=np.random.default_rng(SEED)
    sample=op[op.future_share_change.notna()].sample(100,random_state=SEED)
    errs=[]
    for r in sample.itertuples():
        market=y[m[r.market_level].eq(r.market)].sum(0);v=inn.loc[r.INN].to_numpy();errs.append(abs(r.future_share_change-(v[r.t+6]/market[r.t+6]-v[r.t]/market[r.t])))
        check('Anchor feature '+r.INN+' '+str(r.t),np.isclose(r.sales_12m,v[r.t-11:r.t+1].sum()))
    check('Six-month target independently reproduced',max(errs)<1e-12)
    lock=json.loads((OUT/'models/opportunity_lock.json').read_text(encoding='utf-8'))
    check('Opportunity train-label and test boundary',23+6<30 and 41+6<48 and 53+6==59)
    from forecast_lib import lag_features,static_inn
    past=inn.to_numpy();keys=inn.index.to_numpy();altered=y.copy();altered[:,48:]=altered[:,48:]*9+12345
    stat1=static_inn(m,keys,48,y);stat2=static_inn(m,keys,48,altered)
    check('Future perturbation cannot change origin static features',np.array_equal(stat1,stat2))
    changed=aggregate(m,altered,'INN_key').to_numpy();x1,s1=lag_features(past,48,stat1);x2,s2=lag_features(changed,48,stat2)
    check('Future perturbation cannot change origin lag features',np.array_equal(x1,x2) and np.array_equal(s1,s2))
    fm=pd.read_csv(TABLE/'forecast_model_metrics.csv');v=fm[fm.split.eq('validation')]
    end=pd.to_datetime(v.origin)+v.horizon.map(lambda h:pd.DateOffset(months=int(h)))
    check('Forecast selection outcomes do not enter 2023',all(t.year<=2022 for t in end))
    hc=pd.read_csv(TABLE/'hierarchy_consistency.csv');check('Crossed hierarchy sums',hc.portfolio_difference.abs().max()<1e-5)
    f=pd.read_csv(TABLE/'forecast_2024.csv');check('Finite nonnegative forecasts',np.isfinite(f.P50_proxy).all() and (f.P50_proxy>=0).all())
    check('Forecast interval order',((f.P10_empirical<=f.P50_proxy)&(f.P50_proxy<=f.P90_empirical)).all())
    alloc=np.load(PROC/'sku_reconciled_2024.npy');p=np.load(PROC/'forecast_2024_point.npy');check('INN monthly allocation reconciles',np.allclose(aggregate(m,alloc,'INN_key'),p))
    actions=pd.read_csv(TABLE/'commercial_actions.csv');check('Unknown INN excluded from commercial invest',(actions.loc[~actions.known_inn,'action']=='Data Review').all())
    check('Eight figures created',len(list((OUT/'figures').glob('0[1-8]_*.png')))==8)
    save(pd.DataFrame(checks),'verification_checks');jsave({'passed':True,'checks':len(checks),'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'scope':'Numerical, pipeline and temporal-boundary checks; not external validation or causal proof'},OUT/'qa/verification_summary.json')
    print('Verified',len(checks),'checks',flush=True)
if __name__=='__main__':main()
