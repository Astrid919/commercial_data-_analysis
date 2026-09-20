"""SKU summation for two crossed structures: INN and ATC, not a false nested tree."""
from common import *
from forecast_lib import intermittent

def candidates(y,h):
    return {'Seasonal Naive':np.tile(y[:,-12:],(1,int(np.ceil(h/12))))[:,:h],**intermittent(y,h)}

def main():
    m,y=load();rows=[];errs={};origins=[24,30,36]
    for t in origins:
        p=candidates(y[:,:t],12);inter=(patterns(y[:,:t]).ADI>=1.32).to_numpy()
        for name,v in p.items():
            errs.setdefault(name,[0,0]);errs[name][0]+=np.abs(v[inter]-y[inter,t:t+12]).sum();errs[name][1]+=y[inter,t:t+12].sum()
            rows.append(dict(split='validation',origin=str(MONTHS[t-1].date()),model=name,**metrics(y[inter,t:t+12],v[inter],y[inter,:t])))
    choice=min(errs,key=lambda k:errs[k][0]/errs[k][1]);jsave({'intermittent_model':choice,'non_intermitttent_model':'Seasonal Naive','selection':'pooled 12m validation WAPE for ADI>=1.32'},OUT/'models/sku_forecast_lock.json')
    preds=candidates(y[:,:48],12);ix=(patterns(y[:,:48]).ADI>=1.32).to_numpy()
    for name,p in preds.items():rows.append(dict(split='locked_holdout',origin='2022-12-01',model=name,**metrics(y[ix,48:],p[ix],y[ix,:48])))
    p=preds['Seasonal Naive'].copy();p[ix]=preds[choice][ix]
    bu=aggregate(m,p,'INN_key').to_numpy();actual=aggregate(m,y,'INN_key').to_numpy();direct=np.load(PROC/'holdout_forecast.npy')
    save(pd.DataFrame([dict(method='Direct INN',**metrics(actual[:,48:],direct,actual[:,:48])),dict(method='Bottom-up SKU',**metrics(actual[:,48:],bu,actual[:,:48]))]),'hierarchical_forecast_metrics')
    save(pd.DataFrame(rows),'intermittent_forecast_metrics')
    final=candidates(y,12);ix=(patterns(y).ADI>=1.32).to_numpy();sku=final['Seasonal Naive'].copy();sku[ix]=final[choice][ix]
    np.save(PROC/'sku_bottomup_2024.npy',sku)
    save(pd.DataFrame({'SKU':m.SKU,'forecast_2024':sku.sum(1),'model':np.where(ix,choice,'Seasonal Naive')}),'sku_bottomup_2024')
    # Allocate direct INN point forecasts to SKUs using observed last-12-month mix.
    keys=np.load(PROC/'forecast_keys.npy');p=np.load(PROC/'forecast_2024_point.npy');allocated=np.zeros_like(sku)
    for j,key in enumerate(keys):
        ids=np.flatnonzero(m.INN_key.eq(key));w=y[ids,-12:].sum(1)
        if w.sum()==0:w=y[ids].sum(1)
        if w.sum()==0:w=np.ones(len(ids))
        allocated[ids]=w[:,None]/w.sum()*p[j]
    save(pd.DataFrame({'SKU':m.SKU,'INN':m.INN_key,'ATC4':m.ATC4,'ATC5':m.ATC5,'allocated_direct_2024':allocated.sum(1)}),'sku_reconciled_allocation')
    np.save(PROC/'sku_reconciled_2024.npy',allocated)
    checks=[]
    for key in ['INN_key','ATC5','ATC4']:
        a=aggregate(m,allocated,key);a.columns=[f'2024-{i:02d}' for i in range(1,13)];save(a.reset_index(names=key),'reconciled_'+key.lower())
        checks.append({'level':key,'sum':a.to_numpy().sum(),'portfolio_difference':a.to_numpy().sum()-p.sum()})
    save(pd.DataFrame(checks),'hierarchy_consistency')
if __name__=='__main__':main()
