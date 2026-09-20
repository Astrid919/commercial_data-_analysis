from common import *

def main():
    m,y=load(); annual=y.reshape(len(m),5,12).sum(2)
    p=pd.DataFrame({'year':range(2019,2024),'sales':annual.sum(0)});p['YoY']=p.sales.pct_change();save(p,'portfolio_annual')
    save(pd.DataFrame({'month':MONTHS,'sales':y.sum(0)}),'portfolio_monthly')
    inn=aggregate(m,y,'INN_key');inn.to_parquet(PROC/'inn_monthly.parquet')
    k=pd.DataFrame({'INN':inn.index,'sales_2019':inn.iloc[:,:12].sum(1).values,'sales_2022':inn.iloc[:,36:48].sum(1).values,'sales_2023':inn.iloc[:,48:60].sum(1).values})
    k['known_inn']=~k.INN.str.startswith('UNKNOWN_SKU_'); k['YoY']=growth(k.sales_2023,k.sales_2022);k['CAGR']=divide(k.sales_2023,k.sales_2019)**.25-1
    k['portfolio_share_2023']=k.sales_2023/k.sales_2023.sum()
    for key in ['ATC1','ATC2','ATC4','ATC5']:
        a=aggregate(m,annual,key); a.columns=[f'sales_{i}' for i in range(2019,2024)]
        a['contribution_2023']=a.sales_2023/annual[:,-1].sum();a['YoY']=growth(a.sales_2023,a.sales_2022)
        save(a.reset_index(names=key),'contribution_'+key.lower())
    counts=m.groupby('INN_key').agg(sku_count=('SKU','size'),brand_count=('Brand','nunique'),strength_breadth=('strength_mg','nunique'),form_breadth=('dosage_form','nunique'),pack_breadth=('pack_size','nunique'))
    k=k.merge(counts,left_on='INN',right_index=True);save(k,'inn_performance')
    known=k[k.known_inn].sort_values('sales_2023',ascending=False)
    shares=known.sales_2023/known.sales_2023.sum()
    save(pd.DataFrame([{'Top10_known_INN_share_of_portfolio':known.head(10).sales_2023.sum()/k.sales_2023.sum(),'Top20_known_INN_share_of_portfolio':known.head(20).sales_2023.sum()/k.sales_2023.sum(),'HHI_known_INN_normalized':(shares**2).sum(),'known_INN_volume_coverage':known.sales_2023.sum()/k.sales_2023.sum(),'portfolio_CAGR':(p.sales.iloc[-1]/p.sales.iloc[0])**.25-1}]),'portfolio_concentration')
    # Descriptive largest YoY monthly shifts, not a causal structural-break test.
    z=pd.DataFrame({'month':MONTHS,'sales':y.sum(0)});z['YoY']=z.sales.pct_change(12);save(z.dropna().sort_values('YoY'),'monthly_shifts')
if __name__=='__main__': main()
