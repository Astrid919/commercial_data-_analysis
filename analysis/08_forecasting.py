"""Model selection uses only targets available before 2023; final holdout is frozen."""
from common import *
from forecast_lib import all_forecasts,static_inn
import joblib

def main():
    m,sku=load();inn=aggregate(m,sku,'INN_key');y=inn.to_numpy();keys=inn.index.to_numpy()
    np.save(PROC/'forecast_keys.npy',keys.astype(str))
    origins=[(24,12),(30,12),(36,12),(39,6),(42,6),(45,3)]
    rows=[];cache={};segrows=[]
    for t,h in origins:
        print('Forecast validation origin',MONTHS[t-1],flush=True)
        preds,_=all_forecasts(y[:,:t],h,static_inn(m,keys,t,sku));segs=patterns(y[:,:t]).segment.to_numpy()
        cache[t]=(preds,segs,h)
        np.savez_compressed(OUT/f'models/validation_predictions_{t}.npz',**preds)
        for name,p in preds.items():
            for hh in [3,6,12]:
                if hh<=h:rows.append(dict(split='validation',origin=str(MONTHS[t-1].date()),horizon=hh,model=name,**metrics(y[:,t:t+hh],p[:,:hh],y[:,:t])))
            if h==12:
                for seg in np.unique(segs):
                    ix=segs==seg
                    segrows.append(dict(segment=seg,model=name,absolute_error=np.abs(y[ix,t:t+h]-p[ix]).sum(),actual=y[ix,t:t+h].sum(),series=int(ix.sum())))
    valid=pd.DataFrame(rows);v12=valid[valid.horizon==12];best=v12.groupby('model').WAPE.mean().idxmin()
    sr=pd.DataFrame(segrows).groupby(['segment','model']).sum().reset_index();sr['WAPE']=sr.absolute_error/sr.actual
    choices={seg:g.sort_values('WAPE').iloc[0].model for seg,g in sr.groupby('segment')}
    # Segmentation choices are locked on validation; no use of holdout segment outcomes.
    jsave({'selected_global':best,'segment_models':choices,'selection':'Mean origin WAPE at 12-month horizon','selection_targets_through':'2022-12','locked_holdout':'2023-01 to 2023-12','validation_origins':origins,'ETS':'Additive seasonal adjustment followed by grid-fitted ETS(A,Ad,N); not joint maximum-likelihood seasonal ETS','global_features':'normalized lags 1/2/3/6/12; rolling means 3/6/12; SD6/12; zero rate; ADI; calendar; observed SKU count and median pack/strength/form breadth; INN, dominant ATC3/ATC4/dosage_form categories with top254 origin-volume levels retained and remaining pooled; Ridge uses one-hot, HistGB uses native categorical splits; no future exogenous data'},OUT/'models/forecast_lock.json')
    save(sr,'forecast_segment_validation')
    print('Locked forecast model',best,flush=True)
    hold,models=all_forecasts(y[:,:48],12,static_inn(m,keys,48,sku));seg=patterns(y[:,:48]).segment.to_numpy()
    segmented=np.vstack([hold[choices.get(s,best)][i] for i,s in enumerate(seg)]);hold['Segmented models']=segmented
    for name,p in hold.items():rows.append(dict(split='locked_holdout',origin='2022-12-01',horizon=12,model=name,**metrics(y[:,48:],p,y[:,:48])))
    # Production remains selected global: segmented model is a sensitivity benchmark.
    selected=hold[best];np.save(PROC/'holdout_forecast.npy',selected)
    final,models=all_forecasts(y,12,static_inn(m,keys,60,sku));point=final[best]
    np.save(PROC/'forecast_2024_point.npy',point)
    joblib.dump(models,OUT/'models/forecast_global_models.joblib')
    # Calibration only from 12-month validation paths, signed standardized residuals.
    annual_errors=[];monthly_errors=[]
    for t,(preds,_,h) in cache.items():
        if h!=12:continue
        scale=np.maximum(y[:,t-12:t].sum(1),1)
        annual_errors.append((y[:,t:t+12].sum(1)-preds[best].sum(1))/scale)
        monthly_errors.append((y[:,t:t+12]-preds[best])/np.maximum(y[:,t-12:t].mean(1),1)[:,None])
    ae=np.concatenate(annual_errors);me=np.concatenate(monthly_errors,axis=0)
    # Scale-stratified residual distributions reduce mixing tiny and large series.
    thresholds=np.quantile(y[:,:48].sum(1),[.5,.9]);groups=np.digitize(y[:,:48].sum(1),thresholds)
    annual=np.zeros((len(y),2));holdannual=np.zeros((len(y),2));monthly=np.zeros((len(y),12,2));coverage=[]
    for g in range(3):
        # Group membership for each calibration origin determined from origin history.
        es=[];ems=[]
        for t,(preds,_,h) in cache.items():
            if h!=12:continue
            rank=pd.Series(y[:,:t].sum(1)).rank(pct=True).to_numpy();gi=np.where(rank<=.5,0,np.where(rank<=.9,1,2));ix=gi==g
            es.extend(((y[:,t:t+12].sum(1)-preds[best].sum(1))/np.maximum(y[:,t-12:t].sum(1),1))[ix])
            ems.append(((y[:,t:t+12]-preds[best])/np.maximum(y[:,t-12:t].mean(1),1)[:,None])[ix])
        q=np.quantile(es,[.1,.9]);qm=np.quantile(np.vstack(ems),[.1,.9],axis=0).T
        ix=groups==g;holdannual[ix]=np.maximum(0,selected[ix].sum(1)[:,None]+np.maximum(y[ix,36:48].sum(1),1)[:,None]*q)
        holdannual[ix,0]=np.minimum(holdannual[ix,0],selected[ix].sum(1));holdannual[ix,1]=np.maximum(holdannual[ix,1],selected[ix].sum(1))
        rank=pd.Series(y.sum(1)).rank(pct=True).to_numpy();gf=np.where(rank<=.5,0,np.where(rank<=.9,1,2));ixf=gf==g
        annual[ixf]=np.maximum(0,point[ixf].sum(1)[:,None]+np.maximum(y[ixf,48:].sum(1),1)[:,None]*q)
        monthly[ixf]=np.maximum(0,point[ixf,:,None]+np.maximum(y[ixf,48:].mean(1),1)[:,None,None]*qm)
        truth=y[ix,48:].sum(1);coverage.append(dict(scale_group=g,n_series=int(ix.sum()),annual_80_coverage=((truth>=holdannual[ix,0])&(truth<=holdannual[ix,1])).mean(),mean_interval_width=(holdannual[ix,1]-holdannual[ix,0]).mean()))
    # Bounds bracket the operational point forecast. It is not a fitted conditional median.
    annual[:,0]=np.minimum(annual[:,0],point.sum(1));annual[:,1]=np.maximum(annual[:,1],point.sum(1))
    monthly[:,:,0]=np.minimum(monthly[:,:,0],point);monthly[:,:,1]=np.maximum(monthly[:,:,1],point)
    f=pd.DataFrame({'INN':keys,'known_inn':~pd.Series(keys).str.startswith('UNKNOWN_SKU_'),'actual_2023':y[:,48:].sum(1),'P50_proxy':point.sum(1),'P10_empirical':annual[:,0],'P90_empirical':annual[:,1]})
    f['growth_2024']=growth(f.P50_proxy,f.actual_2023);f['selected_model']=best;save(f,'forecast_2024')
    mo=pd.DataFrame({'INN':np.repeat(keys,12),'month':np.tile(pd.date_range('2024-01-01',periods=12,freq='MS'),len(keys)),'point_forecast':point.ravel(),'P10_empirical':monthly[:,:,0].ravel(),'P90_empirical':monthly[:,:,1].ravel()});save(mo,'forecast_2024_monthly')
    save(pd.DataFrame(rows),'forecast_model_metrics');save(pd.DataFrame(coverage),'forecast_interval_coverage')
    error=np.abs(y[:,48:]-selected);save(pd.DataFrame({'INN':keys,'holdout_WAPE':divide(error.sum(1),y[:,48:].sum(1)),'holdout_bias':divide((selected-y[:,48:]).sum(1),y[:,48:].sum(1))}),'forecast_holdout_by_inn')
    # Portfolio annual interval calibrated on portfolio path errors, never sum marginal quantiles.
    pe=[]
    for t,(preds,_,h) in cache.items():
        if h==12:pe.append((y[:,t:t+12].sum()-preds[best].sum())/y[:,t-12:t].sum())
    lo,hi=point.sum()+np.quantile(pe,[.1,.9])*y[:,48:].sum()
    jsave({'point_2024':point.sum(),'growth_2024':point.sum()/y[:,48:].sum()-1,'P10_scenario':max(0,min(lo,point.sum())),'P90_scenario':max(hi,point.sum()),'calibration_origins':3,'warning':'P50_proxy is a point forecast, not a fitted median. P10/P90 are empirical residual planning bounds, weakly calibrated from three overlapping annual origins; annual quantiles are not summed monthly/INN quantiles.'},OUT/'qa/forecast_summary.json')
if __name__=='__main__':main()
