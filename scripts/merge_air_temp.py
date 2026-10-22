"""Replace MODIS surface temperature in build/data.js with TerraClimate air temperature.
Input: data/lga_air_temp.csv (gee/03_air_temp.js export). Run: python scripts/merge_air_temp.py
Matching: each data.js feature is matched to its row in the older exports (lga_inputs.csv +
lga_season_lst.csv) by value, then to the air-temp CSV by the shared GAUL names. Five LGAs whose
values match no old row are matched by state plus name variant and have all inputs refreshed from the exports."""
import json, os, re, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); P = lambda *a: os.path.join(HERE, '..', *a)
t = open(P('build', 'data.js')).read()
a = re.search(r'(?:var|const)\s+LGA=', t).end(); b = re.search(r';\s*(?:var|const)\s+STATES=', t)
LGA = json.loads(t[a:b.start()]); STATES = json.loads(t[b.end():].rstrip().rstrip(';')); F = LGA['features']
old = pd.read_csv(P('data', 'lga_inputs.csv')).merge(pd.read_csv(P('data', 'lga_season_lst.csv')), on=['ADM1_NAME', 'ADM2_NAME'])
air = pd.read_csv(P('data', 'lga_air_temp.csv')).set_index(['ADM1_NAME', 'ADM2_NAME'])
cols = ['rain', 'dry', 'lst', 'ph', 'oc', 'slope', 'lst_cool', 'lst_wet']; M = old[cols].values
tol = np.array([.06] * 8); used = set(); match = {}
def find(v, skip=()):
    d = np.abs(M - v); ok = np.all([d[:, k] < tol[k] for k in range(8) if k not in skip], axis=0)
    return [j for j in np.where(ok)[0] if j not in used]
for i, f in enumerate(F):
    ok = find(np.array(f['properties']['v'], float))
    if len(ok) == 1: match[i] = ok[0]; used.add(ok[0])
for i, f in enumerate(F):                      # Lagos: pH/OC were imputed, match on the rest
    if i not in match and f['properties']['s'] == 'Lagos':
        ok = find(np.array(f['properties']['v'], float), skip=(3, 4))
        if len(ok) == 1: match[i] = ok[0]; used.add(ok[0])
NAME = {('Kebbi', 'Wasagu-Danko'): ('Kebbi', 'Danko Wasagu'), ('FCT Abuja', 'Municipal Area Council'): ('Abuja', 'Abuja Municipal'),
        ('Kogi', 'Kogi'): ('Kogi', 'Koton-Karfe'), ('Abia', 'Obi Ngwa'): ('Abia', 'Oboma Ngwa'), ('Benue', 'Buruku'): ('Benue', 'Bukuru')}
refreshed = []
for i, f in enumerate(F):
    if i not in match:
        k = NAME[(f['properties']['s'], f['properties']['l'])]
        j = old.index[(old.ADM1_NAME == k[0]) & (old.ADM2_NAME == k[1])][0]; match[i] = j; refreshed.append(f['properties']['l'])
        f['properties']['v'][:6] = [round(float(old.at[j, c]), 1 if c in ('rain', 'dry', 'lst', 'oc') else 2) for c in cols[:6]]
assert len(match) == 774 and len(set(match.values())) == 774, 'join is not one-to-one'
for i, f in enumerate(F):
    r = air.loc[(old.at[match[i], 'ADM1_NAME'], old.at[match[i], 'ADM2_NAME'])]
    v = f['properties']['v']; v[2], v[6], v[7] = round(float(r.tmax_hot), 1), round(float(r.tmax_cool), 1), round(float(r.tmax_wet), 1)
print('matched 774 one-to-one; inputs refreshed from exports for:', refreshed)
dump = lambda o: json.dumps(o, separators=(',', ':'))
open(P('build', 'data.js'), 'w').write(t[:a - len('const LGA=')] + 'const LGA=' + dump(LGA) + ';const STATES=' + dump(STATES) + ';')
