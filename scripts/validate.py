"""Validate AgriZone suitability scores against GBIF presence records.
Run from anywhere:  python validate.py   (needs pandas numpy shapely scikit-learn scipy)
Options (results go to validation_results<suffix>.csv so the default file is not overwritten):
  --soil PATH   replace SoilGrids pH/OC with iSDAsoil from PATH (data/zonal_all.csv) before scoring
  --strict      drop GBIF records that are living/genebank specimens, material samples or citations, have coordinates
                with fewer than 2 decimals (about 1 km; one decimal is about 11 km, as wide as an LGA), are older than 1980 (records with no year are kept), or have a stated
                coordinate uncertainty above 5 km
  --gbif PATH   use a different GBIF file (e.g. data/gbif_nigeria_detailed.csv from gbif_nigeria_detailed.py)
"""
import sys, json, re, os, numpy as np, pandas as pd
from shapely.geometry import shape, Point
from shapely.strtree import STRtree
from sklearn.metrics import roc_auc_score

HERE = os.path.dirname(os.path.abspath(__file__))
P = lambda *a: os.path.join(HERE, '..', *a)
sys.path.insert(0, HERE)
ARGS = sys.argv[1:]
opt = lambda n: ARGS[ARGS.index(n) + 1] if n in ARGS else None
SUF = ('_isda_soil' if opt('--soil') else '') + ('_strict' if '--strict' in ARGS else '') + ('_' + os.path.basename(opt('--gbif')).split('.')[0] if opt('--gbif') else '')

t = open(P('build', 'data.js')).read()
F = json.loads(t[re.search(r'(?:var|const)\s+LGA=', t).end():re.search(r';\s*(?:var|const)\s+STATES=', t).start()])['features']
g = json.load(open(P('build', 'lga_boundaries_simplified.json')))['features']  # same order, simplified geometry
if opt('--soil'):
    iz = pd.read_csv(opt('--soil')).sort_values('id').reset_index(drop=True)   # id-keyed export: align rows by explicit LGA id, not CSV row order
    assert len(iz) == len(F) and np.array_equal(iz.id.values, np.arange(len(F))), 'soil file does not contain sequential LGA ids 0..773'; names_match = sum(iz.l.values == [f['properties']['l'] for f in F]); assert names_match >= len(F) - 5, f'soil file names mismatch too many LGAs: {names_match}/{len(F)}'; print(f'soil export aligned by id; {names_match}/{len(F)} names match (known boundary-name variants may differ)'); n = 0
    for f, (_, r) in zip(F, iz.iterrows()):
        for j, c in ((3, 'isda_ph'), (4, 'isda_oc')):
            if not np.isnan(r[c]): f['properties']['v'][j] = float(r[c]); n += 1
    print(f'soil: {n} pH/OC values replaced with iSDAsoil from {opt("--soil")}')
geoms = [shape(f['geometry']) for f in g]
tree = STRtree(geoms)
W = dict(rain=.32, dry=.15, tmax=.25, ph=.13, oc=.05, slope=.10)
src = open(P('build', 'template.html')).read()
C = {}
for m in re.finditer(r'(\w+):\{n:"[^"]*",rain:(\[[^\]]*\]),dry:(\[[^\]]*\]),tmax:(\[[^\]]*\]),src:"(\w+)",ph:(\[[^\]]*\]),oc:(\[[^\]]*\]),slope:(\[[^\]]*\])', src):
    k = m.group(1)
    C[k] = dict(rain=json.loads(m.group(2)), dry=json.loads(m.group(3)), tmax=json.loads(m.group(4)), src=m.group(5),
                ph=json.loads(m.group(6)), oc=json.loads(m.group(7)), slope=json.loads(m.group(8)))

def tr(x, e):
    if x <= e[0] or x >= e[3]: return 0
    if x < e[1]: return (x - e[0]) / (e[1] - e[0])
    if x <= e[2]: return 1
    return (e[3] - x) / (e[3] - e[2])

names = ['rain', 'dry', 'tmax', 'ph', 'oc', 'slope']
def sc(v, c):
    w = list(v[:6]); w[2] = v[{'tmax': 2, 'tmax_cool': 6, 'tmax_wet': 7}[c['src']]]
    s = {k: tr(x, c[k]) for k, x in zip(names, w)}
    return sum(W[k] * s[k] for k in W) * np.sqrt(min(s.values())), min(s, key=lambda k: (s[k], -W[k]))

S = {k: np.array([sc(f['properties']['v'], c)[0] for f in F]) for k, c in C.items()}

def lga_of(lon, lat, tol=0.05):
    p = Point(lon, lat); idx = tree.query(p, predicate='intersects')
    if len(idx): return int(idx[0])
    j = int(tree.nearest(p)); return j if geoms[j].distance(p) < tol else None

# ---------- load and clean GBIF records ----------
def strict_filter(d):
    dec = lambda x: len(('%.6f' % x).rstrip('0').split('.')[1])
    yr = pd.to_numeric(d.year, errors='coerce')
    ok = ~d.basis.isin(['LIVING_SPECIMEN', 'MATERIAL_SAMPLE', 'MATERIAL_CITATION'])
    ok &= (d.lat.map(dec) >= 2) & (d.lon.map(dec) >= 2) & (yr.isna() | (yr >= 1980))
    if 'unc' in d: ok &= d.unc.isna() | (d.unc <= 5000)
    return d[ok]
raw = pd.read_csv(opt('--gbif') or P('data', 'gbif_nigeria.csv'))
d = raw.drop_duplicates(['crop', 'lat', 'lon']).copy()
if '--strict' in ARGS:
    n0 = len(d); d = strict_filter(d).copy(); print(f'--strict: kept {len(d)} of {n0} unique records')   # GBIF returns the same point many times (genebank/duplicate records)
print(f'GBIF rows: {len(raw)} -> {len(d)} after dropping repeated (crop,lat,lon); {len(raw)-len(d)} duplicates removed')
d['i'] = [lga_of(a, b) for a, b in zip(d.lon, d.lat)]
swapped = 0
for ix in d.index[d.i.isna()]:                           # try swapped lat/lon before giving up
    j = lga_of(d.at[ix, 'lat'], d.at[ix, 'lon'], tol=0)   # strict: swapped point must fall inside a polygon
    if j is not None: d.at[ix, 'i'] = j; swapped += 1
bad = d[d.i.isna()]
print(f'outside Nigeria polygons: {len(bad)} dropped ({swapped} rescued by swapping lat/lon)')
if len(bad): print(bad[['crop', 'lat', 'lon', 'basis', 'year']].to_string(index=False))
d = d.dropna(subset=['i']); d['i'] = d.i.astype(int)
print('basisOfRecord:', d.basis.value_counts().to_dict())

# ---------- metrics ----------
rng = np.random.default_rng(1)
area = np.array([f['properties']['a'] for f in F], float); area /= area.sum()
out = []
for k in C:
    p = d[d.crop == k]
    if len(p) < 2: print(f'{k}: {len(p)} records left after filtering, skipped'); continue
    sp = S[k][p.i.values]
    u = np.unique(p.i.values)
    # Presence-background AUC: one positive per occupied LGA; negatives are unoccupied LGAs.
    bg = np.setdiff1d(np.arange(len(F)), u)
    if len(bg) == 0: print(f'{k}: no unoccupied background LGAs, skipped'); continue
    su = S[k][u]; sb = S[k][bg]
    y = np.r_[np.ones(len(u)), np.zeros(len(bg))]; scores = np.r_[su, sb]
    auc = roc_auc_score(y, scores)
    # Bootstrap occupied and unoccupied LGAs separately; interval is descriptive, not spatially blocked.
    boot = []
    for _ in range(500):
        pos = rng.choice(su, len(su), replace=True)
        neg = rng.choice(sb, len(sb), replace=True)
        boot.append(roc_auc_score(np.r_[np.ones(len(pos)), np.zeros(len(neg))], np.r_[pos, neg]))
    lo, hi = np.percentile(boot, [2.5, 97.5])
    rec50, bg50 = (sp >= .6).mean() * 100, (sb >= .6).mean() * 100
    rec75, bg75 = (sp >= .8).mean() * 100, (sb >= .8).mean() * 100
    out.append(dict(crop=k, n=len(p), lgas=len(u), background_lgas=len(bg), rec60=round(rec50,1), bg60=round(bg50,1), lift60=round(rec50 / max(bg50, 0.1), 2),
                    rec80=round(rec75,1), bg80=round(bg75,1), lift80=round(rec75 / max(bg75, 0.1), 2),
                    auc=round(auc,3), auc_lga=round(auc,3), auc_lga_lo=round(lo,3), auc_lga_hi=round(hi,3),
                    reliable='LOW n' if len(u) < 25 else 'indicative'))
r = pd.DataFrame(out); print(); print(r.to_string(index=False))
print('Presence-background AUC compares occupied LGA scores with unoccupied LGA scores. GBIF records are biased presence data, not yield observations; intervals are not spatially blocked.')
r.to_csv(os.path.join(HERE, f'validation_results{SUF}.csv'), index=False)

# ---------- diagnostics: records scoring low ----------
for k in ['cocoa', 'wheat', 'maize', 'tomato']:
    p = d[d.crop == k]; p = p.assign(s=S[k][p.i.values]); b = p[p.s < .25]
    print(k, 'low-score records:', len(b), b.basis.value_counts().to_dict(),
          [(g[j]['properties']['l'], g[j]['properties']['s']) for j in b.i.unique()[:6]])
print('\n--- wheat presence LGAs (limiting factor)')
p = d[d.crop == 'wheat']
for i2, n in p.i.value_counts().items():
    f = F[i2]; print(g[i2]['properties']['l'], g[i2]['properties']['s'], n, round(S['wheat'][i2], 2), f['properties']['v'], sc(f['properties']['v'], C['wheat'])[1])
print('\n--- rice records in low-score LGAs: limiting factor')
p = d[d.crop == 'rice']; p = p.assign(s=S['rice'][p.i.values])
print(p.groupby(p.i.map(lambda i: g[i]['properties']['s'])).s.agg(['count', 'mean']).sort_values('count', ascending=False).head(6).round(2))
print(pd.Series([sc(F[i]['properties']['v'], C['rice'])[1] for i in p.i[p.s < .5]]).value_counts().to_dict())
