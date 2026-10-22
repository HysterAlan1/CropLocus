"""Check polygon areas and centroids in build/data.js.   pip install shapely pyproj pandas
  python scripts/check_geometry.py          report only
  python scripts/check_geometry.py --fix    move centroids that fall outside their polygon onto it (point on surface)
Area: compares the 'a' field and the geodesic area of the stored (simplified) polygons, state by state, and the sum
against the published area of Nigeria. If data/lga_gaul_geometry.csv (gee/05_gaul_geometry.js) exists it also
compares against the unsimplified GAUL areas."""
import sys, os, json, numpy as np, pandas as pd
from shapely.geometry import shape, Point
from pyproj import Geod
from common import *
GEOD = Geod(ellps='WGS84'); NIGERIA = 923768   # km2, total area incl. inland water (CIA World Factbook / UN)
geod_km2 = lambda g: abs(GEOD.geometry_area_perimeter(g)[0]) / 1e6
t, L, S = load_data(); F = L['features']; G = [shape(f['geometry']) for f in F]
A = np.array([f['properties']['a'] for f in F], float); GA = np.array([geod_km2(g) for g in G])
print('--- AREA')
print(f"sum of 'a' field             {A.sum():>10,.0f} km2")
print(f"geodesic area of polygons    {GA.sum():>10,.0f} km2  (what the stored geometry actually covers)")
print(f"published area of Nigeria    {NIGERIA:>10,}  km2  (includes inland water)")
print(f"gap, stored polygons vs published: {GA.sum() - NIGERIA:,.0f} km2 ({(GA.sum() / NIGERIA - 1) * 100:.2f}%)")
d = (A - GA) / GA * 100
print(f"'a' vs polygon area per LGA: median {np.median(d):.2f}%, worst {d[np.argmax(np.abs(d))]:.1f}% ({F[int(np.argmax(np.abs(d)))]['properties']['l']}); LGAs off by more than 5%: {int((np.abs(d) > 5).sum())}")
sa = pd.DataFrame({'s': [f['properties']['s'] for f in F], 'a_field': A, 'poly': GA}).groupby('s').sum()
st = {f['properties']['n']: geod_km2(shape(f['geometry'])) for f in S['features']}
sa['state_outline'] = pd.Series(st); sa['outline_vs_lgas_%'] = ((sa.state_outline / sa.poly - 1) * 100).round(1)
print('states where the state outline and the sum of its LGA polygons differ by more than 3%:'); print(sa[sa['outline_vs_lgas_%'].abs() > 3].round(0).to_string() or 'none')
gp = P('data', 'lga_gaul_geometry.csv')
if os.path.exists(gp):
    g = pd.read_csv(gp); tot = g.area_km2.sum(); lc = g[g.ADM2_NAME.str.lower() == 'lake chad'].area_km2.sum()
    print(f"GAUL geodesic area, all rows       {tot:>10,.0f} km2  (includes the 'Lake chad' row, {lc:,.0f} km2, which the app drops)")
    print(f"stored polygons minus GAUL (all)   {GA.sum() - tot:>10,.0f} km2  -> simplification and boundary-source differences, {(GA.sum() / tot - 1) * 100:+.2f}%")
    print(f"published area minus GAUL (all)    {NIGERIA - tot:>10,.0f} km2  ({(NIGERIA / tot - 1) * 100:.2f}%) -> a gap that GAUL itself has, so it is not caused by this app's simplification or by Lake chad")
else: print('(run gee/05_gaul_geometry.js and save the CSV as data/lga_gaul_geometry.csv for the GAUL comparison)')
print('\n--- CENTROIDS')
bad = [i for i, g in enumerate(G) if not g.covers(Point(F[i]['properties']['c']))]
for i in bad:
    p = F[i]['properties']; print(f"  outside polygon: {p['l']} ({p['s']}), {G[i].distance(Point(p['c'])) * 111:.1f} km from it, {G[i].geom_type}")
print(f'{len(bad)} of {len(F)} centroids outside their polygon (the app does not use them).')
if '--fix' in sys.argv and bad:
    for i in bad: F[i]['properties']['c'] = [round(c, 3) for c in G[i].representative_point().coords[0]]
    a = t.index('const LGA=') + len('const LGA='); b = t.index(';const STATES=')
    open(P('build', 'data.js'), 'w').write(t[:a] + json.dumps(L, separators=(',', ':')) + t[b:]); print('fixed; rebuild index.html')
