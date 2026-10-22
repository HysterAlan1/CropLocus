// CropLocus: ALL inputs per LGA, computed on the polygons the map actually draws, keyed by integer id.
// Why: gee/01-05 used FAO GAUL polygons, and the app joined them to its own polygons by name/value. 334 of 774 LGAs
// failed at least one join test (area ratio 0.64-1.46 at 5-95%; 65 GAUL centroids fall in a different LGA; 5 LGAs
// were matched by name similarity). Running the statistics on the drawn polygons removes the join altogether.
//
// STEP 1  Code Editor > Assets > NEW > Table upload > data/lga_polygons_for_gee.geojson
//         (properties: id 0..773, l = LGA name, s = state). Paste the asset path below.
// STEP 2  Run. Two exports appear in Tasks: agrizone_zonal_all (all land) and agrizone_zonal_cropland (ESA WorldCover
//         class 40 only). Save them in data/ as zonal_all.csv and zonal_cropland.csv (cropland one is optional).
// STEP 3  python scripts/apply_export.py            (all land, same method as before)
//         python scripts/apply_export.py --cropland (cropland-weighted, falls back to all land where cropland is scarce)
var ASSET = 'projects/YOUR_PROJECT/assets/agrizone_lga_polygons';   // <-- EDIT THIS

var lgas = ee.FeatureCollection(ASSET);
print('LGAs:', lgas.size());                                          // expect 774

// ---------- rainfall: CHIRPS 2015-2024, mean of the ten annual monthly totals ----------
var chirps = ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY');
var years = ee.List.sequence(2015, 2024);
var monthly = ee.ImageCollection(ee.List.sequence(1, 12).map(function (m) {
  return ee.ImageCollection(years.map(function (y) {
    return chirps.filter(ee.Filter.calendarRange(y, y, 'year'))
                 .filter(ee.Filter.calendarRange(m, m, 'month')).sum();
  })).mean();
}));
var rain = monthly.sum().rename('rain');
var dry = monthly.map(function (i) { return i.lt(50); }).sum().rename('dry');         // used by the app
var dry100 = monthly.map(function (i) { return i.lt(100); }).sum().rename('dry100');  // cocoa/oil palm literature

// ---------- air temperature: TerraClimate 2015-2024 (deg C after x0.1) ----------
var tc = ee.ImageCollection('IDAHO_EPSCOR/TERRACLIMATE').filterDate('2015-01-01', '2025-01-01')
  .select(['tmmx', 'tmmn']).map(function (i) { return i.multiply(0.1).copyProperties(i, ['system:time_start']); });
var tmmx = tc.select('tmmx'), tmmn = tc.select('tmmn');
var tmaxHot = ee.ImageCollection(years.map(function (y) {
  return tmmx.filter(ee.Filter.calendarRange(y, y, 'year')).max();
})).mean().rename('tmax_hot');
var cool = ee.Filter.or(ee.Filter.calendarRange(11, 12, 'month'), ee.Filter.calendarRange(1, 2, 'month'));
var wet = ee.Filter.calendarRange(6, 10, 'month');
var tmaxCool = tmmx.filter(cool).mean().rename('tmax_cool');
var tmaxWet = tmmx.filter(wet).mean().rename('tmax_wet');
function tmean(f) { return tmmx.filter(f).mean().add(tmmn.filter(f).mean()).divide(2); }
var tmeanCool = tmean(cool).rename('tmean_cool');   // for wheat/tomato if their ranges are mean temperatures
var tmeanWet = tmean(wet).rename('tmean_wet');

// ---------- terrain ----------
var dem = ee.Image('NASA/NASADEM_HGT/001').select('elevation');
var slope = ee.Terrain.slope(dem).multiply(Math.PI / 180).tan().multiply(100).rename('slope');

// ---------- SoilGrids, 0-30 cm, DEPTH-WEIGHTED (5, 10, 15 cm layers) ----------
// 01_lga_inputs.js averaged the three layers with equal weight, which over-weights the top 5 cm and is inconsistent
// with the iSDA script below (20 cm + 10 cm). Gaps (urban Lagos etc.) are filled with a 5 km focal mean.
function sg(asset, p, div) {
  var im = ee.Image(asset);
  return im.select(p + '_0-5cm_mean').multiply(5).add(im.select(p + '_5-15cm_mean').multiply(10))
           .add(im.select(p + '_15-30cm_mean').multiply(15)).divide(30).divide(div);
}
var phRaw = sg('projects/soilgrids-isric/phh2o_mean', 'phh2o', 10);
var ocRaw = sg('projects/soilgrids-isric/soc_mean', 'soc', 10);
var phFill = phRaw.unmask(phRaw.focalMean(5000, 'circle', 'meters')).rename('ph');
var ocFill = ocRaw.unmask(ocRaw.focalMean(5000, 'circle', 'meters')).rename('oc');
phRaw = phRaw.rename('ph_raw'); ocRaw = ocRaw.rename('oc_raw');   // raw bands tell us which LGAs were gap-filled

// ---------- iSDAsoil (independent check, same depth weights) ----------
var iph = ee.Image('ISDASOIL/Africa/v1/ph');
var isdaPh = iph.select('mean_0_20').multiply(2).add(iph.select('mean_20_50')).divide(3).divide(10).rename('isda_ph');
var ioc = ee.Image('ISDASOIL/Africa/v1/carbon_organic');
function bt(b) { return ioc.select(b).divide(10).exp().subtract(1); }
var isdaOc = bt('mean_0_20').multiply(2).add(bt('mean_20_50')).divide(3).rename('isda_oc');

// ---------- cropland (ESA WorldCover 2021, class 40) ----------
var crop = ee.ImageCollection('ESA/WorldCover/v200').first().select('Map').eq(40);

var base = rain.addBands([dry, dry100, tmaxHot, tmaxCool, tmaxWet, tmeanCool, tmeanWet, slope, dem.rename('elev'),
                          phFill, ocFill, phRaw, ocRaw, isdaPh, isdaOc]);

// ---------- export 1: all land (1 km sampling, same method as before) ----------
var all = base.reduceRegions({collection: lgas, reducer: ee.Reducer.mean(), scale: 1000, tileScale: 8});
// ---------- export 2: cropland only (250 m sampling) + cropland fraction ----------
var cropImg = base.updateMask(crop).addBands(crop.unmask(0).rename('crop_frac'));
var cr = cropImg.reduceRegions({collection: lgas, reducer: ee.Reducer.mean(), scale: 250, tileScale: 16});

var cols = ['id', 'l', 's', 'rain', 'dry', 'dry100', 'tmax_hot', 'tmax_cool', 'tmax_wet', 'tmean_cool', 'tmean_wet',
            'slope', 'elev', 'ph', 'oc', 'ph_raw', 'oc_raw', 'isda_ph', 'isda_oc'];
print('null rain (all):', all.filter(ee.Filter.notNull(['rain']).not()).size());        // expect 0
print('null ph after fill (all):', all.filter(ee.Filter.notNull(['ph']).not()).size());   // expect 0
print('null oc after fill (all):', all.filter(ee.Filter.notNull(['oc']).not()).size());   // expect 0
print('Kano sample:', all.filter(ee.Filter.eq('s', 'Kano')).limit(2));
print('Ondo sample:', all.filter(ee.Filter.eq('s', 'Ondo')).limit(2));

Export.table.toDrive({collection: all, description: 'agrizone_zonal_all', fileFormat: 'CSV', selectors: cols});
Export.table.toDrive({collection: cr, description: 'agrizone_zonal_cropland', fileFormat: 'CSV',
                      selectors: cols.concat(['crop_frac'])});
