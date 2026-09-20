"""Eight report figures and a reproducible therapeutic market deep dive."""
from common import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager,ticker

font=Path('C:/Windows/Fonts/msyh.ttc')
if font.exists():font_manager.fontManager.addfont(str(font));plt.rcParams['font.family']=font_manager.FontProperties(fname=str(font)).get_name()
plt.rcParams.update({'axes.spines.top':False,'axes.spines.right':False,'axes.unicode_minus':False,'font.size':15,'axes.titlesize':17,'figure.facecolor':'white'})
COLORS=['#167C80','#285B8A','#CB8C32','#AE535C','#746494','#6A777F']
def read(name):return pd.read_csv(TABLE/(name+'.csv'))
def finish(fig,name):
    fig.tight_layout(pad=1.7);fig.savefig(OUT/'figures'/name,dpi=180,bbox_inches='tight');plt.close(fig)
def short(s,n=34):return s if len(s)<=n else s[:n-1]+'…'

def main():
    m,y=load();k=read('commercial_actions');annual=read('portfolio_annual');monthly=read('portfolio_monthly');fm=read('forecast_model_metrics');opp=read('opportunity_model_metrics')
    fig,ax=plt.subplots(1,2,figsize=(12.8,4.3));ax[0].bar(annual.year.astype(str),annual.sales/1e6,color=COLORS[0])
    for i,r in annual.iterrows():ax[0].text(i,r.sales/1e6+12,f'{r.sales/1e6:,.1f}',ha='center',fontsize=14)
    ax[0].set(ylabel='原始销量单位 / 百万',title='年度销量');ax[0].set_ylim(0,annual.sales.max()/1e6*1.15)
    ax[1].plot(pd.to_datetime(monthly.month),monthly.sales/1e6,color=COLORS[1]);ax[1].set(ylabel='原始销量单位 / 百万',title='月度销量');ax[1].grid(alpha=.15)
    finish(fig,'01_portfolio_sales.png')
    a=read('contribution_atc1').sort_values('sales_2023').tail(10);fig,ax=plt.subplots(figsize=(12.8,4.7))
    area={'A':'消化道与代谢','N':'神经系统','C':'心血管系统','R':'呼吸系统','M':'肌肉骨骼系统','D':'皮肤科','J':'全身用抗感染药','B':'血液与造血器官','G':'泌尿生殖与性激素','S':'感觉器官'}
    ax.barh([s[0]+' '+area.get(s[0],s[2:]) for s in a.ATC1],a.sales_2023/1e6,color=COLORS[0]);ax.set(xlabel='2023 年销量 / 百万原始单位',title='ATC1 组合贡献前十');finish(fig,'02_atc_landscape.png')
    d=k[k.market.notna()&k.known_inn].copy();fig,ax=plt.subplots(figsize=(12.8,5));ax.scatter(d.market_growth*100,d.share_change_12m*100,s=12+120*d.sales_2023/d.sales_2023.max(),alpha=.5,color=COLORS[1]);ax.axhline(0,color='gray',lw=.8);ax.axvline(0,color='gray',lw=.8)
    ax.set(xlabel='样本同类市场增长率 / %',ylabel='年度同类份额变化 / 百分点',title='市场增长与分子份额变化')
    ax.set_xlim(d.market_growth.quantile(.01)*100-2,d.market_growth.quantile(.99)*100+2);ax.set_ylim(d.share_change_12m.quantile(.01)*100-1,d.share_change_12m.quantile(.99)*100+1)
    ax.text(.01,.01,'显示第1至99百分位；完整极值见结果表',transform=ax.transAxes,fontsize=12,color='gray');finish(fig,'03_market_vs_share.png')
    fig,ax=plt.subplots(figsize=(12.8,5));known=k[k.known_inn]
    for i,g in known.groupby('cluster'):
        ax.scatter(g.PC1,g.PC2,s=17,alpha=.55,color=COLORS[int(i)%6],label=f'C{int(i)} {g.archetype.iloc[0]}')
    ax.set(xlabel='PC1',ylabel='PC2',title='商业组合分群的主成分投影');ax.legend(fontsize=12,loc='best');finish(fig,'04_portfolio_pca.png')
    names=opp.model.unique();fig,ax=plt.subplots(figsize=(12.8,4.7));pos=np.arange(len(names))
    for j,(split,label) in enumerate([('validation_2021H2','验证集'),('locked_test_2023H1','2023 留出集')]):
        a=opp[opp.split.eq(split)].set_index('model').reindex(names);ax.barh(pos+(j-.5)*.34,a['Lift@20'],height=.32,color=COLORS[j],label=label)
    ax.set_yticks(pos,names);ax.axvline(1,color='gray',ls='--');ax.legend();ax.set(xlabel='逐锚点 Lift@20% 的平均值',title='机会模型前20%名单的提升倍数');finish(fig,'05_opportunity_lift.png')
    val=fm[fm.split.eq('validation')&fm.horizon.eq(12)].groupby('model').WAPE.mean();test=fm[fm.split.eq('locked_holdout')].set_index('model').WAPE
    names=val.index.tolist();fig,ax=plt.subplots(figsize=(12.8,4.7));pos=np.arange(len(names));ax.barh(pos-.17,val.reindex(names)*100,height=.32,label='12个月验证 WAPE',color=COLORS[0]);ax.barh(pos+.17,test.reindex(names)*100,height=.32,label='2023 留出 WAPE',color=COLORS[1]);ax.set_yticks(pos,names);ax.set(xlabel='WAPE / %，越低越好',title='需求预测模型比较');ax.legend();finish(fig,'06_forecast_comparison.png')
    fig,ax=plt.subplots(figsize=(12.8,5));actions=['Invest','Emerging Opportunity','Defend','At Risk','Market-led Growth','Monitor']
    for c,act in enumerate(actions):
        g=d[d.action.eq(act)];ax.scatter(g.growth_2024*100,g.share_change_12m*100,s=12+100*g.sales_2023/d.sales_2023.max(),alpha=.6,label=act,color=COLORS[c])
    ax.axhline(0,c='gray',lw=.8);ax.axvline(0,c='gray',lw=.8);ax.set_xlim(-100,min(200,d.growth_2024.quantile(.99)*100+5));ax.set_ylim(d.share_change_12m.quantile(.01)*100-1,d.share_change_12m.quantile(.99)*100+1);ax.set(xlabel='2024 预测增长率 / %',ylabel='年度同类份额变化 / 百分点',title='增长预期与商业行动');ax.legend(fontsize=12,ncol=2);finish(fig,'07_growth_and_actions.png')
    markets=read('atc_market_performance');slices=read('inn_atc4_performance')
    peer_structure=slices[~slices.INN.str.startswith('UNKNOWN_SKU_')].groupby('ATC4').agg(material_peers=('peer_share_2023',lambda s:(s>=.01).sum()),largest_peer=('peer_share_2023','max'))
    markets=markets.merge(peer_structure,on='ATC4');eligible=markets[markets.known_inn_count.between(4,12)&(markets.material_peers>=4)&(markets.largest_peer<.7)]
    selected=eligible.sort_values('sales_2023',ascending=False).iloc[0];market=selected.ATC4;ids=m.index[m.ATC4.eq(market)]
    inn=aggregate(m.loc[ids],y[ids],'INN_key');ay=inn.to_numpy().reshape(len(inn),5,12).sum(2);labels=inn.index.to_numpy();known_ids=np.flatnonzero(~pd.Series(labels).str.startswith('UNKNOWN_SKU_'));top=known_ids[np.argsort(ay[known_ids,-1])[-6:][::-1]];total=ay.sum(0)
    allocated=np.load(PROC/'sku_reconciled_2024.npy');pred=aggregate(m.loc[ids],allocated[ids],'INN_key').sum(axis=1)
    tab=pd.DataFrame({'INN':labels,'sales_2022':ay[:,3],'sales_2023':ay[:,4],'share_2022':ay[:,3]/total[3],'share_2023':ay[:,4]/total[4],'forecast_2024_allocated':pred.reindex(labels).values})
    tab['share_change']=tab.share_2023-tab.share_2022;tab['market_effect']=tab.share_2022*(total[4]-total[3]);tab['share_effect']=total[3]*tab.share_change;tab['interaction']=(total[4]-total[3])*tab.share_change;save(tab,'therapeutic_deep_dive')
    jsave({'ATC4':market,'known_inn_count':int(selected.known_inn_count),'market_growth_2023':total[4]/total[3]-1,'sales_2023':total[4],'forecast_2024_allocated':pred.sum(),'selection_rule':'Largest 2023 ATC4 with 4 to 12 known INNs, at least 4 peers each with >=1% share, largest peer <70%','forecast_note':'INN forecast allocated to SKUs using 2023 volume mix, then aggregated to this ATC4'},OUT/'qa/deep_dive.json')
    fig,axes=plt.subplots(2,2,figsize=(13.5,9.5));axes[0,0].plot(range(2019,2024),total/1e6,marker='o',color=COLORS[0]);axes[0,0].set(title='样本市场年度规模',ylabel='百万原始销量单位');axes[0,0].set_xticks(range(2019,2024))
    for j,i in enumerate(top):axes[0,1].plot(range(2019,2024),ay[i]/total*100,marker='o',color=COLORS[j],label=short(labels[i],25))
    axes[0,1].set(title='主要分子同类份额',ylabel='%');axes[0,1].set_xticks(range(2019,2024));axes[0,1].legend(fontsize=12,loc='lower center',bbox_to_anchor=(.5,.1))
    st=tab.set_index('INN').reindex(labels[top]);yp=np.arange(len(st))
    for j,(c,label) in enumerate([('market_effect','市场效应'),('share_effect','份额效应'),('interaction','交互效应')]):axes[1,0].barh(yp+(j-1)*.23,st[c]/1e6,height=.21,label=label,color=COLORS[j])
    axes[1,0].set_yticks(yp,[short(s,24) for s in st.index],fontsize=12);axes[1,0].set(title='2022至2023增长分解',xlabel='百万原始销量单位');axes[1,0].legend(fontsize=12)
    axes[1,1].barh(yp-.17,st.sales_2023/1e6,height=.32,label='2023 实际',color=COLORS[0]);axes[1,1].barh(yp+.17,st.forecast_2024_allocated/1e6,height=.32,label='2024 分配预测',color=COLORS[1]);axes[1,1].set_yticks(yp,[short(s,24) for s in st.index],fontsize=12);axes[1,1].set(title='主要分子规模与预测',xlabel='百万原始销量单位');axes[1,1].legend(fontsize=12)
    fig.suptitle(short(market,80),fontsize=14);finish(fig,'08_therapeutic_deep_dive.png')
if __name__=='__main__':main()
