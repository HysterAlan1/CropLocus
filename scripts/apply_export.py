"""Put the id-keyed Earth Engine export (gee/06_zonal_on_app_polygons.js) into build/data.js and index.html.
No name or value matching: row `id` is the position of the LGA in data.js.

  python scripts/apply_export.py                       # all-land means  (data/zonal_all.csv)
  python scripts/apply_export.py --cropland            # cropland means where >= MIN_CROP_FRAC cropland, else all land
  python scripts/apply_export.py --dry-run             # report only, write nothing
  python scripts/apply_export.py --all PATH --crop PATH

Checks (the script stops if one fails): 774 unique ids 0..773, LGA and state names agree with data.js,
no missing rain/temperature/slope, values in plausible ranges. Missing soil values keep the value already in data.js.
"""
import sys, os, re, json, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); P = lambda *a: os.path.join(HERE, '..', *a)
A = sys.argv[1:]; opt = lambda n, d=None: A[A.index(n) + 1] if n in A else d
MIN_CROP_FRAC = 0.02                                  # below this the cropland mean rests on too few pixels

t = open(P('build', 'data.js')).read()
a = re.search(r'(?:var|const)\s+LGA=', t).end(); b = re.search(r';\s*(?:var|const)\s+STATES=', t)
head = t[:a - len('const LGA=')]; LGA = json.loads(t[a:b.start()]); STATES = json.loads(t[b.end():].rstrip().rstrip(';')); F = LGA['features']

def load(path):
    d = pd.read_csv(path)
    assert len(d) == 774 and d.id.is_unique and set(d.id) == set(range(774)), f'{path}: need 774 unique ids 0..773, got {len(d)} rows'
    d = d.set_index('id').sort_index()
    for i, f in enumerate(F):
        nn = lambda x: re.sub(r'[^a-z0-9]', '', str(x).lower())   # ids are the key; names are a sanity check, so ignore case and apostrophes (export has Jema''A, map has Jema'a)
        assert nn(d.at[i, 'l']) == nn(f['properties']['l']) and d.at[i, 's'] == f['properties']['s'], f"{path}: id {i} is {d.at[i,'l']} ({d.at[i,'s']}), data.js has {f['properties']['l']} ({f['properties']['s']})"
    return d

allp = opt('--all', P('data', 'zonal_all.csv')); D = load(allp); src = 'all land'
need = ['rain', 'dry', 'tmax_hot', 'tmax_cool', 'tmax_wet', 'slope']
assert not D[need].isna().any().any(), 'missing values:\n' + str(D[need].isna().sum())
if '--cropland' in A:
    C = load(opt('--crop', P('data', 'zonal_cropland.csv'))); use = (C.crop_frac >= MIN_CROP_FRAC) & C[need + ['ph', 'oc']].notna().all(axis=1)
    D = D.copy(); cols = need + ['ph', 'oc']; D.loc[use, cols] = C.loc[use, cols]; src = f'cropland where crop_frac >= {MIN_CROP_FRAC} ({int(use.sum())} LGAs), else all land'
print('source:', src)

old = np.array([f['properties']['v'] for f in F], float); new = old.copy()
col = ['rain', 'dry', 'tmax_hot', 'ph', 'oc', 'slope', 'tmax_cool', 'tmax_wet']; dec = [1, 1, 1, 1, 1, 2, 1, 1]
kept = {'ph': 0, 'oc': 0}
for j, (c, r) in enumerate(zip(col, dec)):
    x = D[c].values.astype(float)
    if c in kept: kept[c] = int(np.isnan(x).sum()); x = np.where(np.isnan(x), old[:, j], x)
    new[:, j] = np.round(x, r)
rng = dict(rain=(300, 4000), dry=(0, 12), tmax_hot=(25, 46), ph=(3.5, 9), oc=(0, 120), slope=(0, 40), tmax_cool=(22, 40), tmax_wet=(22, 40))
for j, c in enumerate(col):
    lo, hi = rng[c]; assert ((new[:, j] >= lo) & (new[:, j] <= hi)).all(), f'{c} outside {lo}-{hi}: ' + str([F[i]['properties']['l'] for i in np.where((new[:, j] < lo) | (new[:, j] > hi))[0]][:5])
assert (new[:, 2] >= new[:, 6]).all() and (new[:, 2] >= new[:, 7]).all(), 'hottest-month max below a seasonal mean'
print('soil values missing in export (kept from data.js): pH', kept['ph'], ' OC', kept['oc'])
if 'ph_raw' in D: print('LGAs gap-filled by the focal mean (no SoilGrids pixel inside):', int(D.ph_raw.isna().sum()), 'pH,', int(D.oc_raw.isna().sum()), 'OC')
print(f"{'input':10s}{'mean change':>13s}{'max |change|':>14s}{'LGAs changed >5%':>18s}")
for j, c in enumerate(col):
    d = new[:, j] - old[:, j]; rel = np.abs(d) / np.maximum(np.abs(old[:, j]), 1e-6)
    print(f'{c:10s}{d.mean():>13.2f}{np.abs(d).max():>14.2f}{int((rel > .05).sum()):>18d}')
if '--dry-run' in A: sys.exit('dry run: nothing written')
for i, f in enumerate(F): f['properties']['v'] = [float(x) for x in new[i]]
dump = lambda o: json.dumps(o, separators=(',', ':'))
body = 'const LGA=' + dump(LGA) + ';const STATES=' + dump(STATES) + ';'
open(P('build', 'data.js'), 'w').write(head + body)
ih = open(P('index.html')).read(); m = re.search(r'const LGA=.*?;const STATES=.*?;(?=\s*</script>)', ih, flags=re.S)
assert m, 'could not find the data block in index.html'
open(P('index.html'), 'w').write(ih[:m.start()] + body + ih[m.end():])
print('wrote build/data.js and index.html (' + src + ')')
