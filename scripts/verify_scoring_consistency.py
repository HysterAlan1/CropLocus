"""Check that full-precision dashboard inputs reproduce the exported adjusted scores."""
import pandas as pd
from common import P, load_data, load_crops, score, cls
_, LGA, _ = load_data()
d = pd.read_csv(P('data','gee_lga_scores_v3.csv')).sort_values('id').reset_index(drop=True)
C = load_crops()
assert len(LGA['features']) == len(d) == 774
max_diff = 0.0; mismatches = 0
for i, f in enumerate(LGA['features']):
    p=f['properties']; r=d.iloc[i]
    assert p['l'].lower().replace("'",'').replace(' ','') == str(r.l).lower().replace("'",'').replace(' ','')
    v=p['v']
    for crop, config in C.items():
        value=score(v,config)
        diff=abs(value-r['score_'+crop]); max_diff=max(max_diff,diff)
        if cls(value)!=int(r['class_'+crop]): mismatches+=1
print(f'LGAs checked: {len(LGA["features"])}; crops checked: {len(C)}; class mismatches: {mismatches}; max score difference: {max_diff:.8f}')
assert mismatches==0 and max_diff<0.00002
