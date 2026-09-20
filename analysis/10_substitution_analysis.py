"""Exploratory availability gaps and peer uplift; no confirmed OOS/causal substitution labels."""
from common import *

def main():
    m,y=load();group={k:g.index.to_numpy() for k,g in m[m.known_inn].groupby('INN')};events=[];pairs=[]
    for name,ids in group.items():
        if len(ids)<2:continue
        total=y[ids].sum(0)
        for i in ids:
            row=y[i];pos=np.flatnonzero(row>0)
            if len(pos)<2:continue
            zero=(row==0);starts=np.flatnonzero(zero & ~np.r_[False,zero[:-1]])
            for start in starts:
                end=start
                while end<60 and row[end]==0:end+=1
                if start<max(3,pos[0]+1) or end>pos[-1]:continue
                peers=total-row;before=peers[start-3:start].mean();during=peers[start:end].mean()
                seasonal=peers[start-12:end-12].mean() if start>=12 else np.nan
                focal_before=row[start-3:start].mean()
                events.append(dict(INN=name,SKU=m.SKU.iloc[i],start=MONTHS[start],end=MONTHS[end-1],duration=end-start,peer_count=len(ids)-1,
                    focal_before_mean=focal_before,peer_before_mean=before,peer_during_mean=during,peer_uplift=divide(during-before,before),
                    peer_seasonal_baseline=seasonal,peer_uplift_vs_prior_year=divide(during-seasonal,seasonal),
                    apparent_absorption_ratio=divide(during-before,focal_before),potential_availability_event=True))
        # Bounded graph exploration: top 8 volume SKUs per INN, all eligible molecules.
        top=ids[np.argsort(y[ids,-12:].sum(1))[-8:]]
        for j,ia in enumerate(top):
            for ib in top[j+1:]:
                a=np.diff(np.log1p(y[ia]));b=np.diff(np.log1p(y[ib]))
                if a.std()==0 or b.std()==0:continue
                corr=np.corrcoef(a,b)[0,1]
                if corr<-.2:pairs.append(dict(INN=name,SKU_A=m.SKU.iloc[ia],SKU_B=m.SKU.iloc[ib],diff_log_correlation=corr,same_form=m.dosage_form.iloc[ia]==m.dosage_form.iloc[ib],strength_A=m.strength_mg.iloc[ia],strength_B=m.strength_mg.iloc[ib]))
    ev=pd.DataFrame(events);save(ev,'substitution_events');save(pd.DataFrame(pairs),'substitution_pairs')
    valid=ev[(ev.peer_before_mean>0)&(ev.focal_before_mean>0)]
    save(valid.groupby('INN').agg(events=('SKU','size'),sku_count=('SKU','nunique'),median_peer_uplift=('peer_uplift','median'),positive_uplift_rate=('peer_uplift',lambda x:(x>0).mean())).reset_index(),'substitution_inn_summary')
    jsave({'events':len(ev),'eligible_inns':ev.INN.nunique(),'positive_peer_uplift_share':float((valid.peer_uplift>0).mean()),'median_peer_uplift':float(valid.peer_uplift.median()),'caution':'No inventory/stockout labels, no untreated control; before/during comparisons are descriptive. Same-INN products may not be clinically substitutable.'},OUT/'qa/substitution_summary.json')
if __name__=='__main__':main()
