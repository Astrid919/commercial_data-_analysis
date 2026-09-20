"""Reproduce the original analysis and audit report tables without altering inputs."""
from pathlib import Path
import json, hashlib, re
import numpy as np
import pandas as pd
from docx import Document

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'outputs/iqvia_teva_case_20260919'
OLD=BASE/'analysis'
NEW=BASE/'verification_20260920/recomputed'
OUT=BASE/'verification_20260920'

def main():
    a=json.loads((OLD/'analysis_results.json').read_text(encoding='utf-8'))
    b=json.loads((NEW/'analysis_results.json').read_text(encoding='utf-8'))
    diffs=[]; counts={'numeric_values':0,'other_values':0}; maxdiff=0
    def compare(x,y,path=''):
        nonlocal maxdiff
        if isinstance(x,dict):
            if set(x)!=set(y): diffs.append(path+' keys')
            for k in x: compare(x[k],y[k],path+'/'+k)
        elif isinstance(x,list):
            if len(x)!=len(y): diffs.append(path+' length')
            for i,(xx,yy) in enumerate(zip(x,y)): compare(xx,yy,path+f'/{i}')
        elif isinstance(x,(int,float)) and not isinstance(x,bool):
            counts['numeric_values']+=1; maxdiff=max(maxdiff,abs(x-y))
            if not np.isclose(x,y,rtol=1e-10,atol=1e-7): diffs.append([path,x,y])
        else:
            counts['other_values']+=1
            if x!=y: diffs.append([path,x,y])
    compare(a,b)
    csv_checks=[]
    for p in OLD.glob('*.csv'):
        x,y=pd.read_csv(p),pd.read_csv(NEW/p.name)
        try:
            pd.testing.assert_frame_equal(x,y,check_exact=False,rtol=1e-10,atol=1e-7)
            status='PASS'
        except AssertionError as e: status=str(e)
        csv_checks.append({'file':p.name,'rows':len(x),'columns':len(x.columns),'result':status})
    doc=Document(BASE/'IQVIA_Pharma_Portfolio_Analytics_Report.docx')
    tables=[]
    pct=lambda x:f'{x:.1%}'
    mil=lambda x:f'{x/1e6:.1f}M'
    pp=lambda x:f'{x*100:.1f} pp'
    def check(ti, rows, start=1):
        actual=[[c.text for c in row.cells] for row in doc.tables[ti].rows][start:]
        expected=[[str(c) for c in row] for row in rows]
        tables.append({'table_index_zero_based':ti,'cells_checked':sum(map(len,expected)),'result':'PASS' if actual==expected else 'FAIL','differences':[(i,x,y) for i,(x,y) in enumerate(zip(actual,expected)) if x!=y]})
    k=pd.DataFrame(b['inn_kpi'])
    check(7,[(r.INN,mil(r.sales_2023),pct(r.yoy_growth_2023),pct(r.portfolio_share_2023),pp(r.portfolio_share_change_2023)) for _,r in k.nlargest(6,'sales_2023').iterrows()])
    peer=pd.DataFrame(b['peer_analysis']); peer=peer[peer.market_name.str.contains('HMG|M01A |N02B ',regex=True)].sort_values(['market_name','share_change_pp'],ascending=[True,False])
    # Source market names are truncated; compare all numeric fields and the INN.
    actual=[[c.text for c in row.cells] for row in doc.tables[8].rows][1:]
    expected=[(r.INN,pct(r.market_growth_2023),pp(r.share_change_pp),f'{r.share_effect:,.0f}') for _,r in peer.iterrows()]
    tables.append({'table_index_zero_based':8,'cells_checked':len(expected)*4,'result':'PASS' if [[x[0],*x[2:]] for x in actual]==[list(x) for x in expected] else 'FAIL'})
    check(10,[(r['cluster_label'],r['INN_count'],mil(r['sales_2023']),pct(r['avg_yoy_growth']),pp(r['avg_share_change']),pct(r['avg_forecast_growth'])) for r in b['cluster_summary']])
    check(12,[(r['model'],pct(r['validation_pr_auc']),pct(r['test_pr_auc']),pct(r['test_precision_top20']),f"{r['test_lift_top20']:.2f}x") for r in b['classification_results']])
    check(13,[(r['feature'],f"{r['pr_auc_drop']:.3f}") for r in b['classification_importance'][:5]])
    check(14,[(r['model'],pct(r['validation_WAPE']),pct(r['test_WAPE']),f"{r['test_MASE']:.2f}",pct(r['test_Bias'])) for r in b['forecast_results']])
    check(16,[(r.INN,mil(r.sales_2023),mil(r.forecast_2024),pct(r.forecast_growth_2024),r.action_segment) for _,r in k.nlargest(8,'forecast_growth_2024').iterrows()])
    raw=pd.read_csv(ROOT/'data/teva_sales_small.csv')
    months=[c for c in raw if re.fullmatch(r'20\d{2} \d{2}',c)]
    totals={str(y):float(raw[[c for c in months if c.startswith(str(y))]].to_numpy().sum()) for y in range(2019,2024)}
    sha=hashlib.sha256((ROOT/'data/teva_sales_small.csv').read_bytes()).hexdigest()
    report_sha=doc.tables[22].rows[2].cells[1].text
    assert len(raw)==raw['Morion ID'].nunique()==1730
    assert all(np.isclose(totals[str(r['year'])],r['sales']) for r in b['portfolio_annual'])
    summary={'recomputed_json':{'counts':counts,'maximum_absolute_difference':maxdiff,'differences':diffs,'result':'PASS' if not diffs else 'FAIL'},'csv_checks':csv_checks,'report_table_checks':tables,'data_sha256':sha,'report_sha256_matches':sha==report_sha,'independent_raw_annual_totals':totals,'forecast_2024_total':float(k.forecast_2024.sum()),'forecast_2024_growth':float(k.forecast_2024.sum()/k.sales_2023.sum()-1),'unique_sku_ids':raw['Morion ID'].nunique(),'runtime':{'numpy':np.__version__,'pandas':pd.__version__},'scope':'Numeric reproducibility does not establish absence of time leakage or external validity.'}
    for f in [ROOT/'data/teva_sales_small.csv',ROOT/'analysis/iqvia_case_analysis.py',ROOT/'analysis/build_report.py',BASE/'IQVIA_Pharma_Portfolio_Analytics_Report.docx']:
        summary.setdefault('file_hashes',[]).append({'path':str(f),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
    OUT.mkdir(exist_ok=True,parents=True)
    (OUT/'verification_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
