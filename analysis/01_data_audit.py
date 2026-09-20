"""Ingest the full source without altering it; preserve every SKU and raw value."""
import re, hashlib
from common import *

def main():
    d=pd.read_csv(SOURCE,dtype={'Morion ID':str,'Brand':str})
    cols=[c for c in d if re.fullmatch(r'20\d{2}[ -]\d{2}',c)]
    assert len(cols)==60 and [c.replace(' ','-') for c in cols]==list(MONTHS.strftime('%Y-%m'))
    assert not d['Morion ID'].duplicated().any(), 'Duplicate SKU IDs require explicit resolution'
    y=d[cols].apply(pd.to_numeric,errors='coerce').to_numpy(float)
    m=d.drop(columns=cols).rename(columns={'Morion ID':'SKU','NFC (1)':'NFC',**{f'ATC Code ({k})':f'ATC{k}' for k in range(1,6)}})
    for c in m:
        m[c]=m[c].fillna('').astype(str).str.replace('\xa0',' ',regex=False).str.strip().str.replace(r'\s+',' ',regex=True)
    m['known_inn']=~m.INN.isin(['','-','NA','N/A'])
    m['INN_key']=np.where(m.known_inn,m.INN,'UNKNOWN_SKU_'+m.SKU)
    quality=pd.DataFrame({'SKU':m.SKU,'missing_rate':np.isnan(y).mean(1),'negative_count':(y<0).sum(1),'zero_rate':(y==0).mean(1),'unknown_inn':~m.known_inn})
    save(quality,'data_quality_by_sku')
    summary={'sku_count':len(m),'inn_raw_labels':m.INN.nunique(),'inn_known_count':m.loc[m.known_inn,'INN'].nunique(),
             'unknown_inn_skus':int((~m.known_inn).sum()),'brand_count':m.Brand.nunique(),'atc4_count':m.ATC4.nunique(),'atc5_count':m.ATC5.nunique(),
             'months':60,'sku_month_observations':int(y.size),'total_sales_2019_2023':float(np.nansum(y)),
             'missing_sales':int(np.isnan(y).sum()),'negative_sales':int((y<0).sum()),'zero_sales':int((y==0).sum()),
             'fractional_sales_observations':int(((y%1)!=0).sum()),'unknown_inn_sales_share':float(y[~m.known_inn].sum()/y.sum())}
    save(pd.DataFrame([summary]),'dataset_summary')
    save(pd.DataFrame({'check':['missing_sales','negative_sales','duplicate_sku','unknown_inn_skus'],'count':[summary['missing_sales'],summary['negative_sales'],0,summary['unknown_inn_skus']]}),'data_quality_summary')
    assert np.isfinite(y).all() and (y>=0).all(), 'Do not silently impute missing/negative sales'
    m.to_parquet(PROC/'sku_attributes.parquet',index=False); np.save(PROC/'sales.npy',y)
    panel=m[['SKU','INN','INN_key','known_inn','ATC3','ATC4','ATC5']].loc[m.index.repeat(60)].reset_index(drop=True)
    panel['Month']=np.tile(MONTHS,len(m)); panel['Sales']=y.ravel()
    panel.to_parquet(PROC/'sku_month_panel.parquet',index=False)
    jsave({'source':str(SOURCE),'sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'summary':summary,'unit':'Original source sales units; case describes packs; fractional values retained; scaling not independently documented'},OUT/'qa/source_manifest.json')
    print(summary,flush=True)
if __name__=='__main__': main()
