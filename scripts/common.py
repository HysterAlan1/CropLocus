"""Shared helpers for the check scripts: read data.js, match LGAs to Earth Engine (GAUL) names, score crops."""
import json, os, re, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); P = lambda *a: os.path.join(HERE, '..', *a)

def load_data():
    t = open(P('build', 'data.js')).read()
    a = re.search(r'(?:var|const)\s+LGA=', t).end(); b = re.search(r';\s*(?:var|const)\s+STATES=', t)
    return t, json.loads(t[a:b.start()]), json.loads(t[b.end():].rstrip().rstrip(';'))

def value_join(F, inputs_csv=None):
    """Match each data.js feature to its (ADM1_NAME, ADM2_NAME) in the Earth Engine exports by rain, dry months,
    slope, pH and organic carbon (blank pH/OC in the export are ignored). Every feature must match exactly one row."""
    old = pd.read_csv(inputs_csv or P('data', 'lga_inputs.csv'))
    M = old[['rain', 'dry', 'slope', 'ph', 'oc']].values; names = list(zip(old.ADM1_NAME, old.ADM2_NAME)); out = []
    for f in F:
        v = f['properties']['v']; d = np.abs(M - np.array([v[0], v[1], v[5], v[3], v[4]], float))
        ok = np.where((d[:, :3] < .06).all(1) & ((d[:, 3:] < .06) | np.isnan(d[:, 3:])).all(1))[0]
        assert len(ok) == 1, f"{f['properties']['s']} / {f['properties']['l']}: {len(ok)} candidate rows"
        out.append(names[ok[0]])
    assert len(set(out)) == len(out), 'two LGAs matched the same export row'
    return out

def load_crops():
    src = open(P('build', 'template.html')).read(); C = {}
    for m in re.finditer(r'(\w+):\{n:"[^"]*",rain:(\[[^\]]*\]),dry:(\[[^\]]*\]),tmax:(\[[^\]]*\]),src:"(\w+)",ph:(\[[^\]]*\]),oc:(\[[^\]]*\]),slope:(\[[^\]]*\])', src):
        C[m.group(1)] = dict(rain=json.loads(m.group(2)), dry=json.loads(m.group(3)), tmax=json.loads(m.group(4)), src=m.group(5),
                             ph=json.loads(m.group(6)), oc=json.loads(m.group(7)), slope=json.loads(m.group(8)))
    return C

W = dict(rain=.32, dry=.15, tmax=.25, ph=.13, oc=.05, slope=.10); TIDX = {'tmax': 2, 'tmax_cool': 6, 'tmax_wet': 7}
def trap(x, e):
    if x <= e[0] or x >= e[3]: return 0
    if x < e[1]: return (x - e[0]) / (e[1] - e[0])
    if x <= e[2]: return 1
    return (e[3] - x) / (e[3] - e[2])
def score(v, c):
    a = dict(rain=v[0], dry=v[1], tmax=v[TIDX[c['src']]], ph=v[3], oc=v[4], slope=v[5]); s = {k: trap(a[k], c[k]) for k in W}
    return sum(W[k] * s[k] for k in W) * np.sqrt(min(s.values()))
cls = lambda s: 3 if s >= .8 else 2 if s >= .6 else 1 if s >= .4 else 0
