from common import *
def main():
    m,y=load();s=patterns(y);s.insert(0,'SKU',m.SKU);s.insert(1,'INN',m.INN_key);save(s,'demand_segments')
    inn=aggregate(m,y,'INN_key');a=patterns(inn.to_numpy());a.insert(0,'INN',inn.index);save(a,'inn_demand_segments')
    save(s.groupby('segment').agg(sku_count=('SKU','size'),mean_zero_rate=('zero_rate','mean'),mean_cv=('CV','mean')).reset_index(),'demand_segment_summary')
if __name__=='__main__': main()
