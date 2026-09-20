"""Descriptive clusters plus separately governed, transparent commercial rules."""
from common import *
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.metrics import silhouette_score
from sklearn.decomposition import PCA
import joblib

def main():
    k=pd.read_csv(TABLE/'inn_performance.csv');k=k.merge(pd.read_csv(TABLE/'inn_demand_segments.csv'),on='INN',how='left')
    peer=pd.read_csv(TABLE/'inn_peer_performance.csv');k=k.merge(peer[['INN','market_level','market','market_growth','peer_share_2023','share_change_3m','share_change_6m','share_change_12m']],on='INN',how='left')
    f=pd.read_csv(TABLE/'forecast_2024.csv').drop(columns=['known_inn']);k=k.merge(f,on='INN',how='left').merge(pd.read_csv(TABLE/'opportunity_2024.csv')[['INN','opportunity_probability','predicted_share_change_6m']],on='INN',how='left')
    k=k.merge(pd.read_csv(TABLE/'forecast_holdout_by_inn.csv'),on='INN',how='left')
    k['relative_growth']=k.YoY-k.market_growth
    cols=['sales_2023','YoY','CAGR','share_change_3m','share_change_6m','share_change_12m','market_growth','relative_growth','CV','seasonality_strength','zero_rate','sku_count','brand_count','strength_breadth','form_breadth','growth_2024']
    ix=k.known_inn;data=k.loc[ix,cols].replace([np.inf,-np.inf],np.nan).copy();data['sales_2023']=np.log1p(data.sales_2023)
    # Winsorization limits extreme ratios for descriptive segmentation only.
    bounds={c:[data[c].quantile(.01),data[c].quantile(.99)] for c in cols}
    for c in cols:data[c]=data[c].clip(*bounds[c])
    imputer=SimpleImputer(strategy='median');scaler=StandardScaler();z=scaler.fit_transform(imputer.fit_transform(data))
    fits={};scores=[]
    for n in range(3,7):
        model=KMeans(n_clusters=n,n_init=20,random_state=SEED).fit(z);score=silhouette_score(z,model.labels_);scores.append({'K':n,'silhouette':score});fits[n]=model
    save(pd.DataFrame(scores),'cluster_selection');best=max(scores,key=lambda r:r['silhouette'])['K'];model=fits[best]
    pca=PCA(n_components=2).fit(z);pc=pca.transform(z);k.loc[ix,'cluster']=model.labels_;k.loc[ix,'PC1']=pc[:,0];k.loc[ix,'PC2']=pc[:,1]
    k['archetype']='Unknown INN'
    labels={}
    for cid,g in k[ix].groupby('cluster'):
        if g.zero_rate.median()>.25 or g.CV.median()>1.2:label='Niche / Volatile'
        elif g.YoY.median()<-.1:label='Declining / Lifecycle'
        elif g.share_change_12m.median()<-.005:label='At Risk'
        elif g.sales_2023.median()>k.loc[ix,'sales_2023'].quantile(.75):label='Mature Leaders'
        elif g.YoY.median()>.1:label='Growth Leaders'
        else:label='Emerging / Mixed'
        labels[int(cid)]=label;k.loc[k.cluster==cid,'archetype']=label
    joblib.dump({'model':model,'imputer':imputer,'scaler':scaler,'pca':pca,'features':cols,'winsor_bounds':bounds},OUT/'models/portfolio_clusters.joblib')
    jsave({'selected_K':best,'PCA_variance_explained':pca.explained_variance_ratio_,'cluster_labels':labels,'purpose':'Descriptive, never directly converted to recommended action'},OUT/'qa/cluster_summary.json')
    # Eligibility and model reliability gate are distinct from the probability ranking.
    opp=pd.read_csv(TABLE/'opportunity_model_metrics.csv');lock=json.loads((OUT/'models/opportunity_lock.json').read_text(encoding='utf-8'))
    test=opp[(opp.model==lock['classifier'])&opp.split.eq('locked_test_2023H1')].iloc[0]
    reliable=bool(test['Lift@20']>1)
    validprob=k.opportunity_probability.notna();threshold=k.loc[validprob,'opportunity_probability'].quantile(.8)
    large=k.sales_2023>=k.loc[ix,'sales_2023'].quantile(.75);high=k.opportunity_probability>=threshold
    k['action']='Monitor';k['reason']='常规跟踪销量与生命周期信号'
    def rule(mask,action,reason):k.loc[mask,'action']=action;k.loc[mask,'reason']=reason
    rule((k.YoY>0)&(k.share_change_12m.abs()<=.002),'Market-led Growth','销量增长且同类份额变化不超过0.2个百分点')
    rule((k.share_change_12m<0)&(k.growth_2024<0),'At Risk','同类份额与预测销量同时下降，核查原因')
    rule(large&(k.share_change_12m<0),'Defend','已知INN规模位于前25%，但同类份额下降')
    rule(reliable&high&(k.share_change_12m>0)&~large,'Emerging Opportunity','机会概率位于前20%，份额上升且规模尚未进入前25%，先验证增长驱动')
    rule(reliable&high&(k.share_change_12m>0)&(k.growth_2024>0)&large,'Invest','机会概率位于前20%，份额及预测销量增长，维持或评估增加商业支持')
    k['supply_watch']=(k.growth_2024>.1)&((k.CV>1)|(k.zero_rate>.2))&(k.holdout_bias<-.1)
    rule(~k.known_inn,'Data Review','补齐INN后再形成分子级商业建议')
    rule(k.known_inn&k.market.isna(),'Monitor','跨多个ATC3或不足3个同类INN，竞争份额不适用')
    save(k,'commercial_actions');save(k[ix],'portfolio_clusters')
    core=['INN','known_inn','actual_2023','P50_proxy','P10_empirical','P90_empirical','growth_2024','share_change_12m','opportunity_probability','predicted_share_change_6m','action','supply_watch','reason']
    save(k[core].sort_values('actual_2023',ascending=False),'forecast_2024_decision_table')
    save(k.groupby('action').agg(inn_or_unknown_sku_count=('INN','size'),sales_2023=('sales_2023','sum'),forecast_2024=('P50_proxy','sum'),supply_watch_count=('supply_watch','sum')).reset_index(),'commercial_action_summary')
    jsave({'opportunity_top_fraction':.2,'current_volume_top_fraction':.25,'flat_share_tolerance':.002,'supply_forecast_growth':.1,'supply_cv':1,'supply_zero_rate':.2,'supply_negative_bias':-.1,'opportunity_holdout_lift20':test['Lift@20'],'opportunity_ranking_enabled':reliable,'cluster_drives_action':False},OUT/'qa/decision_rules.json')
if __name__=='__main__':main()
