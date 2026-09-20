"""Map unambiguous INNs into sampled peer markets; never treat sample as national market."""
from common import *

def main():
    m,y=load(); mappings=[]
    for inn,g in m[m.known_inn].groupby('INN'):
        a4=g.ATC4.unique();a3=g.ATC3.unique()
        # Peer count must be rechecked using observed history at each anchor.
        if len(a4)==1:
            peers=m.loc[m.ATC4.eq(a4[0])&m.known_inn,'INN'].nunique()
            if peers>=3: level,key='ATC4',a4[0]
            elif len(a3)==1: level,key='ATC3',a3[0]
            else: level,key='Excluded','ambiguous_taxonomy'
        elif len(a3)==1: level,key='ATC3',a3[0]
        else: level,key='Excluded','multiple_ATC3'
        peers=m.loc[m[level].eq(key)&m.known_inn,'INN'].nunique() if level!='Excluded' else 0
        if peers<3: level,key='Excluded',key
        mappings.append({'INN':inn,'market_level':level,'market':key,'peer_count_roster':peers,'n_atc4':len(a4),'n_atc3':len(a3)})
    mapping=pd.DataFrame(mappings);save(mapping,'inn_market_mapping')
    mapping.to_parquet(PROC/'inn_market_mapping.parquet',index=False)
    rows=[];decomp=[];inn=aggregate(m,y,'INN_key')
    for r in mapping.itertuples():
        if r.market_level=='Excluded': continue
        mask=m[r.market_level].eq(r.market);v=y[mask].sum(0);a=inn.loc[r.INN].to_numpy()
        M0,M1=v[36:48].sum(),v[48:].sum();Y0,Y1=a[36:48].sum(),a[48:].sum()
        s0,s1=divide(Y0,M0),divide(Y1,M1)
        r0=dict(INN=r.INN,market_level=r.market_level,market=r.market,market_sales_2022=M0,market_sales_2023=M1,market_growth=growth(M1,M0),peer_share_2022=s0,peer_share_2023=s1,share_change_12m=s1-s0)
        for n in [3,6]: r0[f'share_change_{n}m']=float(divide(a[-n:].sum(),v[-n:].sum())-divide(a[-2*n:-n].sum(),v[-2*n:-n].sum()))
        rows.append(r0)
        effects=dict(r0,sales_2022=Y0,sales_2023=Y1,delta_sales=Y1-Y0,market_effect=s0*(M1-M0),share_effect=M0*(s1-s0),interaction=(M1-M0)*(s1-s0))
        effects['reconciliation_error']=effects['delta_sales']-sum(effects[k] for k in ['market_effect','share_effect','interaction'])
        effects['growth_type']='Defend' if M1>M0 and s1<s0 else ('Structural Decline' if M1<M0 and s1<s0 else ('Share-led Growth' if effects['share_effect']>effects['market_effect'] else 'Market-led Growth'))
        decomp.append(effects)
    save(pd.DataFrame(rows),'inn_peer_performance');save(pd.DataFrame(decomp),'growth_decomposition')
    a=pd.read_csv(TABLE/'contribution_atc4.csv');peer=m[m.known_inn].groupby('ATC4').INN.nunique()
    a['known_inn_count']=a.ATC4.map(peer).fillna(0).astype(int);a['eligible_competitive']=a.known_inn_count>=3;save(a,'atc_market_performance')
    # Complete INN x ATC4 views, including cross-market molecules for the deep dive.
    pieces=[]
    for key,g in m.groupby('ATC4'):
        z=aggregate(g,y[g.index], 'INN_key'); totals=z.sum(0)
        for name,row in z.iterrows():
            pieces.append(dict(ATC4=key,INN=name,sales_2022=row.iloc[36:48].sum(),sales_2023=row.iloc[48:].sum(),peer_share_2023=divide(row.iloc[48:].sum(),totals.iloc[48:].sum()),peer_share_2022=divide(row.iloc[36:48].sum(),totals.iloc[36:48].sum())))
    save(pd.DataFrame(pieces),'inn_atc4_performance')
if __name__=='__main__': main()
