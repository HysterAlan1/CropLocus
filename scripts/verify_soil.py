"""Compare SoilGrids pH and organic carbon (what the app uses) with iSDAsoil, an independent African soil map
trained on African field samples (Hengl et al. 2021, Sci Rep 11:6130).
Needs data/zonal_all.csv (export of gee/09_agrizone_corrected_inline.js or gee/08).   python scripts/verify_soil.py [csv]
Neither map is a measurement. Agreement between them is evidence, disagreement is a flag. Outputs data/soil_check.csv."""
import sys, numpy as np, pandas as pd
from scipy.stats import pearsonr, spearmanr
from common import *
t, L, S = load_data(); F = L['features']; C = load_crops()
Z = pd.read_csv(sys.argv[1] if len(sys.argv) > 1 else P('data', 'zonal_all.csv')).set_index('id').sort_index()   # export of gee/09 (id = row in data.js)
assert len(Z) == len(F) and all(Z.l.values == [f['properties']['l'] for f in F]), 'export does not line up with data.js'
df = pd.DataFrame({'state': [f['properties']['s'] for f in F], 'lga': [f['properties']['l'] for f in F],
    'ph_sg': [f['properties']['v'][3] for f in F], 'oc_sg': [f['properties']['v'][4] for f in F],
    'ph_isda': Z.isda_ph.values, 'oc_isda': Z.isda_oc.values,
    'ph_imputed': Z.ph_raw.isna().values, 'oc_imputed': Z.oc_raw.isna().values})   # imputed = no SoilGrids pixel, gap-filled
print(f"iSDA missing: pH {df.ph_isda.isna().sum()} LGAs, OC {df.oc_isda.isna().sum()} LGAs (of {len(df)})\n")
for v, name in [('ph', 'Soil pH'), ('oc', 'Organic carbon, g/kg')]:
    d = df[~df[f'{v}_imputed'] & df[f'{v}_isda'].notna()]; a, b = d[f'{v}_sg'], d[f'{v}_isda']
    print(f"== {name}  (n={len(d)}, imputed and missing LGAs excluded)")
    print(f"   Pearson r {pearsonr(a, b)[0]:.2f}   Spearman r {spearmanr(a, b)[0]:.2f}   bias SoilGrids - iSDA {np.mean(a - b):+.2f}   MAE {np.mean(np.abs(a - b)):.2f}   RMSE {np.sqrt(np.mean((a - b) ** 2)):.2f}")
    print(f"   spread (SD)   SoilGrids {a.std():.2f}   iSDA {b.std():.2f}   ratio {a.std() / b.std():.2f}   (below 1 = SoilGrids is the smoother map)")
    print(f"   5th-95th pct  SoilGrids {a.quantile(.05):.2f}-{a.quantile(.95):.2f}   iSDA {b.quantile(.05):.2f}-{b.quantile(.95):.2f}")
    if v == 'ph': print(f"   LGAs where the two differ by more than 0.5 pH: {(np.abs(a - b) > .5).sum()}  ({(np.abs(a - b) > .5).mean() * 100:.0f}%)")
    else: print(f"   LGAs where one is more than twice the other: {((a / b > 2) | (b / a > 2)).sum()}  ({((a / b > 2) | (b / a > 2)).mean() * 100:.0f}%)")
    print('   mean difference by region (SoilGrids - iSDA), largest first:')
    m = d.assign(diff=a - b).groupby('state')['diff'].mean().round(2); m = m.reindex(m.abs().sort_values(ascending=False).index).head(6)
    print('      ' + m.to_string().replace('\n', '\n      '), '\n')
print('== The 8 Lagos LGAs where the app fills missing soil values with the Lagos mean; iSDA values for them:')
print(df[df.ph_imputed | df.oc_imputed][['lga', 'ph_sg', 'ph_isda', 'oc_sg', 'oc_isda']].round(1).to_string(index=False), '\n')
sc = lambda rows, c: [score(r, c) for r in rows]
V0 = [f['properties']['v'] for f in F]; V1 = [list(v) for v in V0]
for i, v in enumerate(V1):
    if not np.isnan(df.ph_isda[i]): v[3] = float(df.ph_isda[i])
    if not np.isnan(df.oc_isda[i]): v[4] = float(df.oc_isda[i])
print('== Effect on suitability if iSDA soil replaced SoilGrids soil (other inputs unchanged)')
print(f"{'crop':9s}{'mean |score change|':>21s}{'LGAs changing class':>21s}{'class drops':>13s}{'class gains':>13s}")
for k, c in C.items():
    s0, s1 = np.array(sc(V0, c)), np.array(sc(V1, c)); c0, c1 = np.array([cls(x) for x in s0]), np.array([cls(x) for x in s1])
    print(f"{k:9s}{np.abs(s1 - s0).mean():>21.3f}{(c0 != c1).sum():>14d} ({(c0 != c1).mean() * 100:3.0f}%){(c1 < c0).sum():>13d}{(c1 > c0).sum():>13d}")
df['ph_diff'] = df.ph_sg - df.ph_isda; df['oc_ratio'] = df.oc_sg / df.oc_isda
df[(df.ph_diff.abs() > .5) | (df.oc_ratio > 2) | (df.oc_ratio < .5)].to_csv(P('data', 'soil_check.csv'), index=False)
print('\nLGAs with a large disagreement: data/soil_check.csv. To see the effect on GBIF validation: python scripts/validate.py --soil data/lga_isda_soil.csv')
