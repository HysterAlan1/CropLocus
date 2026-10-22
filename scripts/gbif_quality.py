"""Report quality problems in the GBIF records and how many each filter removes.  python scripts/gbif_quality.py [csv]
Works on data/gbif_nigeria.csv (crop, lat, lon, basis, year) or on data/gbif_nigeria_detailed.csv, which adds
unc (coordinate uncertainty, m), institution, dataset and issues."""
import sys, pandas as pd
from common import P
d = pd.read_csv(sys.argv[1] if len(sys.argv) > 1 else P('data', 'gbif_nigeria.csv'))
dec = lambda x: len(('%.6f' % x).rstrip('0').split('.')[1])
yr = pd.to_numeric(d.year, errors='coerce'); d['dups'] = d.duplicated(['crop', 'lat', 'lon'])
d['no_year'] = yr.isna(); d['pre1980'] = yr < 1980; d['low_precision'] = (d.lat.map(dec) < 2) | (d.lon.map(dec) < 2)
d['whole_degree'] = (d.lat % 1 == 0) & (d.lon % 1 == 0); d['specimen_or_sample'] = d.basis.isin(['LIVING_SPECIMEN', 'MATERIAL_SAMPLE', 'MATERIAL_CITATION'])
flags = ['dups', 'no_year', 'pre1980', 'low_precision', 'whole_degree', 'specimen_or_sample']
if 'unc' in d: d['unc_over_5km'] = d.unc > 5000; flags.append('unc_over_5km')
u = d[~d.dups]
print(f'{len(d)} rows, {len(u)} unique (crop, lat, lon).\n\nShare of UNIQUE records with each problem (low_precision = fewer than 2 decimals, about 11 km or worse), by crop (%):')
t = u.groupby('crop')[[f for f in flags if f != 'dups']].mean().mul(100).round(0).astype(int); t.insert(0, 'n', u.groupby('crop').size()); print(t.to_string())
print('\nbasisOfRecord (unique records):'); print(pd.crosstab(u.crop, u.basis).to_string())
if 'institution' in d: print('\nTop institutions per crop (unique records):'); print(u.groupby('crop').institution.agg(lambda s: s.value_counts().head(3).to_dict()).to_string())
rep = d.groupby(['crop', 'lat', 'lon']).size().sort_values(ascending=False).head(5); print('\nMost repeated coordinates (crop, lat, lon: rows):'); print(rep.to_string())
