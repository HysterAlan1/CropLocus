// Google Earth Engine Code Editor: unsimplified GAUL area and centroid per LGA, plus national totals.
// Used by scripts/check_geometry.py (area gap) and scripts/check_join.py (are the name matches right?).
var gaul = ee.FeatureCollection('FAO/GAUL/2015/level2').filter(ee.Filter.eq('ADM0_NAME', 'Nigeria'));
var rows = gaul.map(function (f) {
  var g = f.geometry(), c = g.centroid(100).coordinates();
  return ee.Feature(null, {
    ADM1_NAME: f.get('ADM1_NAME'), ADM2_NAME: f.get('ADM2_NAME'),
    lon: c.get(0), lat: c.get(1), area_km2: g.area(100).divide(1e6)
  });
});
print('GAUL level 2 rows:', rows.size());                                   // expect 775 (774 LGAs + Lake chad)
print('GAUL level 2 area sum, km2:', rows.aggregate_sum('area_km2'));
print('Lake chad row, km2:', rows.filter(ee.Filter.eq('ADM2_NAME', 'Lake chad')).aggregate_sum('area_km2'));
print('GAUL level 0 Nigeria, km2:', ee.FeatureCollection('FAO/GAUL/2015/level0')
  .filter(ee.Filter.eq('ADM0_NAME', 'Nigeria')).geometry().area(100).divide(1e6));
print('US State Dept LSIB Nigeria, km2:', ee.FeatureCollection('USDOS/LSIB_SIMPLE/2017')
  .filter(ee.Filter.eq('country_na', 'Nigeria')).geometry().area(100).divide(1e6));
Export.table.toDrive({
  collection: rows, description: 'agrizone_lga_gaul_geometry', fileFormat: 'CSV',
  selectors: ['ADM1_NAME', 'ADM2_NAME', 'lon', 'lat', 'area_km2']
});
