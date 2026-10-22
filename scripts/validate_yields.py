"""Independent state-yield check against NAERLS/FMAFS 2024 wet-season yields.

Uses published 2024 yield/ha as an external benchmark, not as a direct suitability label.
State means are area-weighted means of LGA scores. Outputs raw-index and adjusted-score rank
correlations side by side; it does not fit weights or claim causal/predictive validity.
"""
import os
import numpy as np
import pandas as pd
from scipy.stats import spearmanr, pearsonr
HERE=os.path.dirname(os.path.abspath(__file__))
P=lambda *a: os.path.join(HERE,'..',*a)
y=pd.read_csv(P('data','official_state_yields_2024.csv'))
y['state']=y['state'].replace({'FCT':'FCT Abuja','C/Rivers':'Cross River'})
s=pd.read_csv(P('data','gee_lga_scores_v3.csv'))
rows=[]
for crop,g in y.groupby('crop'):
    scorecols={'raw':'raw_score_'+crop,'adjusted':'score_'+crop}
    state_scores=[]
    for state,lg in s.groupby('s'):
        state_scores.append({'state':state,'raw':np.average(lg[scorecols['raw']],weights=lg.a),'adjusted':np.average(lg[scorecols['adjusted']],weights=lg.a)})
    st=pd.DataFrame(state_scores)
    m=g.merge(st,on='state',how='inner')
    for method in ['raw','adjusted']:
        rho=spearmanr(m[method],m.yield_mt_ha).statistic
        pear=pearsonr(m[method],m.yield_mt_ha).statistic
        rng=np.random.default_rng(1701)
        boot=[]
        for _ in range(500):
            ix=rng.integers(0,len(m),len(m))
            if len(np.unique(m.yield_mt_ha.iloc[ix]))>1:
                boot.append(spearmanr(m[method].iloc[ix],m.yield_mt_ha.iloc[ix]).statistic)
        lo,hi=np.nanpercentile(boot,[2.5,97.5])
        rows.append({'crop':crop,'score_method':method,'n_states':len(m),'spearman_rho':rho,'spearman_ci_low':lo,'spearman_ci_high':hi,'pearson_r':pear,'yield_source_year':2024,'interpretation':'external ecological/agricultural consistency check only; state yield also reflects inputs, irrigation, varieties, pests, prices, and reporting'})
out=pd.DataFrame(rows)
out.to_csv(P('scripts','yield_validation_results.csv'),index=False,float_format='%.4f')
print(out.to_string(index=False,formatters={'spearman_rho':'{:.3f}'.format,'spearman_ci_low':'{:.3f}'.format,'spearman_ci_high':'{:.3f}'.format,'pearson_r':'{:.3f}'.format}))
