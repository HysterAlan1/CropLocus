"""Clean up build/data.js. Safe to re-run.

 - declares the datasets with `const` and adds the schema comment above
 - fixes geometry: drops degenerate rings, repairs self-intersections,
   winds exterior rings counter-clockwise and holes clockwise (RFC 7946)
 - keeps coordinates at 3 decimals (~110 m; the polygons are simplified to ~3 km
   vertex spacing, so more decimals would add bytes but no accuracy)
Run: python scripts/normalize_data.py   (needs shapely)
"""
import json, os, re
from shapely.geometry import shape, mapping
from shapely.validation import make_valid

HERE = os.path.dirname(os.path.abspath(__file__)); PATH = os.path.join(HERE, '..', 'build', 'data.js')

HEADER = """/* AgriZone data: two GeoJSON FeatureCollections (WGS84, [lon, lat], 3 decimals, simplified boundaries).
 * LGA.features[i].properties (774 LGAs, same order as build/lga_boundaries_simplified.json):
 *   l  LGA name            s  state name
 *   c  centroid [lon, lat] a  area, km2
 *   v  [0] rain      mean annual rainfall, mm            CHIRPS 2015-2024
 *      [1] dry       dry months per year (rain < 50 mm), counted in each year then averaged 2015-2024
 *      [2] tmax      air temp, C, mean daily max in the hottest month of each year  TerraClimate 2015-2024
 *      [3] ph        soil pH, 0-30 cm, thickness-weighted    SoilGrids
 *      [4] oc        organic carbon, g/kg, 0-30 cm, thickness-weighted  SoilGrids
 *      [5] slope     mean slope, %                       NASADEM
 *      [6] tmax_cool mean daily max air temp Nov-Feb, C   TerraClimate
 *      [7] tmax_wet  mean daily max air temp Jun-Oct, C   TerraClimate
 * STATES.features[i].properties: n = state name (outlines only).
 * Source: gee/09_agrizone_corrected_inline.js, statistics on these same polygons (row id = feature index), exported to data/zonal_all.csv
 * and applied with scripts/apply_export.py. 10 LGAs had no SoilGrids pixel and were filled from neighbours (5/25 km focal mean);
 * Agege (Lagos) still had none and keeps its earlier value (pH 5.4, OC 31 g/kg, the SoilGrids scale for Lagos).
 * Rebuild: run gee/09 (or 08), save the CSVs in data/, then python scripts/apply_export.py. */
"""

def ring_area(r):  # signed shoelace area; > 0 means counter-clockwise
    return 0.5 * sum(r[k][0] * r[k + 1][1] - r[k + 1][0] * r[k][1] for k in range(len(r) - 1))

def rnd(r): return [[round(x, 3), round(y, 3)] for x, y in r]

def fix_polygon(rings):
    rings = [rnd(r) for r in rings if len(r) >= 4 and abs(ring_area(r)) > 1e-12]  # drop degenerate rings
    out = []
    for k, r in enumerate(rings):
        want_ccw = (k == 0)
        out.append(r if (ring_area(r) > 0) == want_ccw else r[::-1])
    return out

def fix_geometry(g):
    polys = [g['coordinates']] if g['type'] == 'Polygon' else g['coordinates']
    polys = [p for p in (fix_polygon(p) for p in polys) if p]
    geom = {'type': 'Polygon', 'coordinates': polys[0]} if len(polys) == 1 else {'type': 'MultiPolygon', 'coordinates': polys}
    if not shape(geom).is_valid:  # e.g. self-intersecting ring
        v = make_valid(shape(geom))
        parts = [p for p in getattr(v, 'geoms', [v]) if p.geom_type in ('Polygon', 'MultiPolygon') and not p.is_empty]
        polys = []
        for p in parts:
            for q in (p.geoms if p.geom_type == 'MultiPolygon' else [p]):
                polys.append(fix_polygon([list(map(list, q.exterior.coords))] + [list(map(list, h.coords)) for h in q.interiors]))
        geom = {'type': 'Polygon', 'coordinates': polys[0]} if len(polys) == 1 else {'type': 'MultiPolygon', 'coordinates': polys}
    return geom

t = open(PATH).read()
a = re.search(r'(?:var|const)\s+LGA=', t).end()
b = re.search(r';\s*(?:var|const)\s+STATES=', t)
LGA = json.loads(t[a:b.start()]); STATES = json.loads(t[b.end():].rstrip().rstrip(';'))

fixed = 0
for fc in (LGA, STATES):
    for f in fc['features']:
        g = fix_geometry(f['geometry'])
        if g != f['geometry']: fixed += 1
        f['geometry'] = g
        assert shape(g).is_valid, f['properties']
print('geometries changed:', fixed)

dump = lambda o: json.dumps(o, separators=(',', ':'))
open(PATH, 'w').write(HEADER + 'const LGA=' + dump(LGA) + ';const STATES=' + dump(STATES) + ';')
print('wrote', os.path.normpath(PATH))
