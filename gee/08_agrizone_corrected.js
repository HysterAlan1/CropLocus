
// =====================================================================================================
// CropLocus: CORRECTED Earth Engine pipeline (inputs -> crop tables -> suitability -> limiting factor -> exports)
// Merges the pasted "corrected" script (dry months counted per year, then averaged) with the fixes it lacked:
//   * slope and elevation (the app needs slope; the pasted script dropped it)
//   * SoilGrids layers weighted by thickness (5/10/15 cm) instead of an equal average, gaps filled by 5 km focal mean
//   * statistics on the polygons the map draws, keyed by integer id (no name join; GAUL names are not unique keys)
//   * cropland-only means (WorldCover class 40), iSDA soil check, mean temperature, dry months at 50 and 100 mm
//   * crop threshold table, weights and scoring inside the script, with limiting factor per LGA
// Small file: polygons come from an asset (one upload) or from GAUL (no upload, names instead of ids).
// =====================================================================================================

// ---------------------------------------------- SETTINGS ----------------------------------------------
var USE_CROPLAND = false;       // true: use cropland-only means where WorldCover cropland >= MIN_CROP_FRAC
var MIN_CROP_FRAC = 0.02;
var Y0 = 2015, Y1 = 2024;       // climate years
var DRY_MM = 50;                // a month is "dry" below this rainfall (README suggests 100 for cocoa/oil palm)
var DRY_METHOD = 'annual';      // 'annual' = count dry months in each year, then average (pasted script; recommended)
                                // 'climatology' = count months whose 10-year mean rain is below DRY_MM (what data.js used)
var POLYGONS = 'ASSET';         // 'ASSET' = uploaded id-keyed polygons (recommended); 'GAUL' = FAO GAUL, no upload
var ASSET = 'projects/YOUR_PROJECT/assets/agrizone_lga_polygons';   // <-- EDIT: upload data/lga_polygons_for_gee.geojson

// -------------------------------------------- TABLE 1: weights ----------------------------------------
// Factor weights (sum = 1) and class cut-offs.
var WEIGHTS = {rain: 0.32, dry: 0.15, tmax: 0.25, ph: 0.13, oc: 0.05, slope: 0.10};
// Raw weighted index is retained; the displayed score is penalized by sqrt(minimum factor membership).
var CLASS_CUTS = [0.4, 0.6, 0.8];   // conservative adjusted index: Unsuitable < 0.4 <= Marginal < 0.6 <= Moderate < 0.8 <= High
var CLASS_NAMES = ['Unsuitable', 'Marginal', 'Moderate', 'High'];

// -------------------------------------------- TABLE 2: crops ------------------------------------------
// Each range is [zero below, optimum starts, optimum ends, zero above]. `src` is the temperature statistic used:
//   tmax = hottest-month mean daily max, tmax_cool = Nov-Feb mean daily max, tmax_wet = Jun-Oct mean daily max.
// Oil palm / cocoa dry-month range is on the DRY_MM scale above.
var CROPS = {
  cocoa: {name: 'Cocoa', src: 'tmax', rain: [1100, 1500, 2500, 3200], dry: [-1, 0, 3, 7], tmax: [10, 20, 33, 40], ph: [4.3, 5.5, 7, 7.8], oc: [3,10,35,80], slope: [-1, 0, 30, 45]},
  wheat: {name: 'Wheat', src: 'tmax_cool', rain: [200, 350, 1000, 1400], dry: [-1, 0, 12, 13], tmax: [11, 18, 28, 38], ph: [5, 6, 7.5, 8.3], oc: [2,8,30,80], slope: [-1, 0, 10, 20]},
  cassava: {name: 'Cassava', src: 'tmax', rain: [600, 1000, 1800, 3000], dry: [-1, 0, 5, 9], tmax: [15, 22, 38, 46], ph: [4.3, 5.5, 7.5, 8.5], oc: [2,6,30,80], slope: [-1, 0, 15, 30]},
  rice: {name: 'Rainfed lowland rice', src: 'tmax_wet', rain: [800, 1200, 2200, 3000], dry: [-1, 0, 6, 9], tmax: [24, 30, 38, 44], ph: [4.3, 5.5, 7.5, 8.5], oc: [2,8,30,80], slope: [-1, 0, 5, 12]},
  sorghum: {name: 'Sorghum', src: 'tmax_wet', rain: [300, 500, 1100, 1600], dry: [-1, 0, 8, 10], tmax: [21, 28, 41, 46], ph: [4.8, 5.5, 8, 8.8], oc: [2,5,25,70], slope: [-1, 0, 15, 30]},
  oilpalm: {name: 'Oil palm', src: 'tmax', rain: [1200, 1800, 3000, 4000], dry: [-1, 0, 2, 4], tmax: [18, 24, 34, 40], ph: [4, 5, 6.5, 7.5], oc: [4,10,35,80], slope: [-1, 0, 15, 30]},
  maize: {name: 'Maize', src: 'tmax_wet', rain: [500, 700, 1500, 2500], dry: [-1, 0, 5, 8], tmax: [18, 24, 36, 44], ph: [5, 5.8, 7.5, 8.2], oc: [2,8,30,80], slope: [-1, 0, 12, 25]},
  tomato: {name: 'Irrigated tomato', src: 'tmax_cool', rain: [300, 500, 1500, 2500], dry: [-1, 0, 12, 13], tmax: [16, 24, 33, 41], ph: [5, 6, 7, 8], oc: [3,8,30,80], slope: [-1, 0, 10, 20]}
};

// ------------------------------------ TABLE 3: remedies (shown for limiting factors) -------------------
var FIX = {rain: 'irrigation', dry: 'irrigation', tmax: 'none at field scale', ph: 'liming', oc: 'organic matter', slope: 'terracing'};
var FACTORS = ['rain', 'dry', 'tmax', 'ph', 'oc', 'slope'];

// ---------------------------------------------- POLYGONS ----------------------------------------------
// ASSET: properties id (0..773, same order as build/data.js), l (LGA), s (state).
// GAUL: no upload, but ids are assigned here by sorted names and the values must be joined to the app by name.
var lgas;
if (POLYGONS === 'ASSET') {
  lgas = ee.FeatureCollection(ASSET);
} else {
  var g = ee.FeatureCollection('FAO/GAUL/2015/level2').filter(ee.Filter.eq('ADM0_NAME', 'Nigeria'))
    .filter(ee.Filter.neq('ADM2_NAME', 'Lake chad'));
  var gl = g.toList(1000);
  lgas = ee.FeatureCollection(ee.List.sequence(0, g.size().subtract(1)).map(function (i) {
    var f = ee.Feature(gl.get(i)); return f.set({id: i, l: f.get('ADM2_NAME'), s: f.get('ADM1_NAME')});
  }));
}
print('LGAs (expect 774):', lgas.size());

// ---------------------------------------------- INPUT LAYERS ------------------------------------------
var years = ee.List.sequence(Y0, Y1);
// Rainfall: CHIRPS daily. Annual totals and per-year dry-month counts, then averaged over the years.
var chirps = ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY').select('precipitation')
  .filterDate(Y0 + '-01-01', (Y1 + 1) + '-01-01');
var annual = ee.ImageCollection(years.map(function (y) {
  y = ee.Number(y);
  var yc = chirps.filter(ee.Filter.calendarRange(y, y, 'year'));
  var mt = ee.ImageCollection(ee.List.sequence(1, 12).map(function (m) {
    return yc.filter(ee.Filter.calendarRange(m, m, 'month')).sum().rename('m');
  }));
  return mt.sum().rename('rain')
    .addBands(mt.map(function (i) { return i.lt(DRY_MM); }).sum().rename('dry_a'))
    .addBands(mt.map(function (i) { return i.lt(100); }).sum().rename('dry100_a'));
}));
var rain = annual.select('rain').mean().rename('rain');
// climatology method: month is dry if its 10-year mean rain is below the threshold
var monthly = ee.ImageCollection(ee.List.sequence(1, 12).map(function (m) {
  return ee.ImageCollection(years.map(function (y) {
    return chirps.filter(ee.Filter.calendarRange(y, y, 'year')).filter(ee.Filter.calendarRange(m, m, 'month')).sum();
  })).mean();
}));
var dryClim = monthly.map(function (i) { return i.lt(DRY_MM); }).sum().rename('dry_clim');
var dryAnn = annual.select('dry_a').mean().rename('dry_annual');
var dry = (DRY_METHOD === 'annual' ? dryAnn : dryClim).rename('dry');
var dry100 = (DRY_METHOD === 'annual' ? annual.select('dry100_a').mean()
  : monthly.map(function (i) { return i.lt(100); }).sum()).rename('dry100');

// Air temperature: TerraClimate tmmx/tmmn (x0.1 = deg C)
var tc = ee.ImageCollection('IDAHO_EPSCOR/TERRACLIMATE').filterDate(Y0 + '-01-01', (Y1 + 1) + '-01-01')
  .select(['tmmx', 'tmmn']).map(function (i) { return i.multiply(0.1).copyProperties(i, ['system:time_start']); });
var tmmx = tc.select('tmmx'), tmmn = tc.select('tmmn');
var cool = ee.Filter.or(ee.Filter.calendarRange(11, 12, 'month'), ee.Filter.calendarRange(1, 2, 'month'));
var wet = ee.Filter.calendarRange(6, 10, 'month');
var tmaxHot = ee.ImageCollection(years.map(function (y) {
  return tmmx.filter(ee.Filter.calendarRange(y, y, 'year')).max();
})).mean().rename('tmax');
var tmaxCool = tmmx.filter(cool).mean().rename('tmax_cool');
var tmaxWet = tmmx.filter(wet).mean().rename('tmax_wet');
function tmean(f) { return tmmx.filter(f).mean().add(tmmn.filter(f).mean()).divide(2); }
var tmeanCool = tmean(cool).rename('tmean_cool'), tmeanWet = tmean(wet).rename('tmean_wet');

// Terrain: NASADEM slope in percent
var dem = ee.Image('NASA/NASADEM_HGT/001').select('elevation');
var slope = ee.Terrain.slope(dem).multiply(Math.PI / 180).tan().multiply(100).rename('slope');

// Soil: SoilGrids 0-30 cm, thickness-weighted; gaps filled by 5 km focal mean (raw band kept to flag the gaps)
function sg(asset, p) {
  var im = ee.Image(asset);
  return im.select(p + '_0-5cm_mean').multiply(5).add(im.select(p + '_5-15cm_mean').multiply(10))
           .add(im.select(p + '_15-30cm_mean').multiply(15)).divide(30).divide(10);   // pH x10 -> pH ; dg/kg -> g/kg
}
var phRaw = sg('projects/soilgrids-isric/phh2o_mean', 'phh2o'), ocRaw = sg('projects/soilgrids-isric/soc_mean', 'soc');
var phFill = phRaw.unmask(phRaw.focalMean(5000, 'circle', 'meters')).unmask(phRaw.focalMean(25000, 'circle', 'meters')).rename('ph');
var ocFill = ocRaw.unmask(ocRaw.focalMean(5000, 'circle', 'meters')).unmask(ocRaw.focalMean(25000, 'circle', 'meters')).rename('oc');
phRaw = phRaw.rename('ph_raw'); ocRaw = ocRaw.rename('oc_raw');

// iSDAsoil (independent check only; not used in the score)
var iph = ee.Image('ISDASOIL/Africa/v1/ph');
var isdaPh = iph.select('mean_0_20').multiply(2).add(iph.select('mean_20_50')).divide(3).divide(10).rename('isda_ph');
var ioc = ee.Image('ISDASOIL/Africa/v1/carbon_organic');
function bt(b) { return ioc.select(b).divide(10).exp().subtract(1); }
var isdaOc = bt('mean_0_20').multiply(2).add(bt('mean_20_50')).divide(3).rename('isda_oc');

// Cropland: ESA WorldCover 2021 class 40
var crop = ee.ImageCollection('ESA/WorldCover/v200').first().select('Map').eq(40);

var base = rain.addBands([dry, dryAnn, dryClim, dry100, tmaxHot, tmaxCool, tmaxWet, tmeanCool, tmeanWet, slope, dem.rename('elev'),
                          phFill, ocFill, phRaw, ocRaw, isdaPh, isdaOc]);

// ---------------------------------------------- ZONAL STATISTICS --------------------------------------
var allLand = base.reduceRegions({collection: lgas, reducer: ee.Reducer.mean(), scale: 1000, tileScale: 8});
var cropLand = base.updateMask(crop).addBands(crop.unmask(0).rename('crop_frac'))
  .reduceRegions({collection: lgas, reducer: ee.Reducer.mean(), scale: 250, tileScale: 16});

var VARS = ['rain', 'dry', 'dry_annual', 'dry_clim', 'dry100', 'tmax', 'tmax_cool', 'tmax_wet', 'tmean_cool', 'tmean_wet', 'slope', 'elev', 'ph', 'oc'];
var inputs = allLand;
if (USE_CROPLAND) {
  var joined = ee.Join.saveFirst('c').apply({primary: allLand, secondary: cropLand,
    condition: ee.Filter.equals({leftField: 'id', rightField: 'id'})});
  inputs = ee.FeatureCollection(joined).map(function (f) {
    var c = ee.Feature(f.get('c'));
    var frac = ee.Number(ee.Algorithms.If(c.get('crop_frac'), c.get('crop_frac'), 0));
    var ok = frac.gte(MIN_CROP_FRAC);
    VARS.forEach(function (v) { ok = ok.and(ee.Number(ee.Algorithms.If(c.get(v), 1, 0))); });
    var out = f;
    VARS.forEach(function (v) { out = out.set(v, ee.Algorithms.If(ok, c.get(v), f.get(v))); });
    return out.set('crop_frac', frac).set('used_cropland', ok);
  });
}
inputs = inputs.map(function (f) { return f.set('a', f.geometry().area(100).divide(1e6)); });   // area, km2

// ---------------------------------------------- SCORING (server side) ----------------------------------
// Trapezoid membership: 0 outside e[0]..e[3], 1 inside e[1]..e[2], linear between. Identical to the app.
function trap(x, e) {
  x = ee.Number(x);
  return ee.Number(1).min(x.subtract(e[0]).divide(e[1] - e[0])).min(ee.Number(e[3]).subtract(x).divide(e[3] - e[2])).max(0);
}
function scoreCrop(f, key) {
  var c = CROPS[key];
  var vals = {rain: f.get('rain'), dry: f.get('dry'), tmax: f.get(c.src), ph: f.get('ph'), oc: f.get('oc'), slope: f.get('slope')};
  var s = {}, weighted = ee.Number(0), minFactor = ee.Number(1);
  var sortKeys = [];
  FACTORS.forEach(function (k) {
    s[k] = trap(vals[k], c[k]); weighted = weighted.add(s[k].multiply(WEIGHTS[k]));
    minFactor = minFactor.min(s[k]);
    sortKeys.push(s[k].subtract(WEIGHTS[k] * 1e-6));      // ties go to the heavier factor
  });
  // Limiting-factor adjustment: retain the weighted index but penalize the weakest factor.
  var total = weighted.multiply(minFactor.sqrt());
  var keys = ee.List(sortKeys);
  var lim = ee.List(FACTORS).get(keys.indexOf(keys.reduce(ee.Reducer.min())));
  var klass = total.gte(CLASS_CUTS[0]).add(total.gte(CLASS_CUTS[1])).add(total.gte(CLASS_CUTS[2]));   // 0..3
  var out = f.set('raw_score_' + key, weighted).set('score_' + key, total).set('class_' + key, klass).set('limiting_' + key, lim);
  FACTORS.forEach(function (k) { out = out.set('s_' + key + '_' + k, s[k]); });
  return out;
}
// Last resort for an LGA that still has no soil value after both focal fills (flagged, scoring only; the
// zonal_all export keeps the blank so apply_export.py keeps the value already in data.js).
var PH_FALLBACK = 5.9, OC_FALLBACK = 15;
var scored = inputs.map(function (f) {
  var noPh = ee.Algorithms.IsEqual(f.get('ph'), null), noOc = ee.Algorithms.IsEqual(f.get('oc'), null);
  return f.set('ph', ee.Algorithms.If(noPh, PH_FALLBACK, f.get('ph'))).set('oc', ee.Algorithms.If(noOc, OC_FALLBACK, f.get('oc')))
          .set('soil_fallback', ee.Number(ee.Algorithms.If(noPh, 1, 0)).max(ee.Number(ee.Algorithms.If(noOc, 1, 0))));
});
Object.keys(CROPS).forEach(function (key) { scored = scored.map(function (f) { return scoreCrop(f, key); }); });

// ---------------------------------------------- CHECKS IN THE CONSOLE ----------------------------------
['rain', 'ph', 'oc', 'slope'].forEach(function (v) {
  print('null ' + v + ' (expect 0):', inputs.filter(ee.Filter.notNull([v]).not()).size());
});
print('Gap-filled LGAs, SoilGrids pH / OC:', allLand.filter(ee.Filter.notNull(['ph_raw']).not()).size(),
      allLand.filter(ee.Filter.notNull(['oc_raw']).not()).size());                      // README: 7 / 8 had no pixel
['Kano', 'Ondo', 'Edo'].forEach(function (st) {
  var sub = scored.filter(ee.Filter.eq('s', st));
  print(st + ': mean cocoa score (README: Kano 0.24, Ondo 0.90, Edo 0.89)', sub.aggregate_mean('score_cocoa'));
});
// State x crop table: area-weighted mean score
var states = ee.List(scored.aggregate_array('s').distinct());
var stateTable = ee.FeatureCollection(states.map(function (st) {
  var sub = scored.filter(ee.Filter.eq('s', st)), area = ee.Number(sub.aggregate_sum('a'));
  var props = {state: st, n_lga: sub.size(), area_km2: area};
  Object.keys(CROPS).forEach(function (key) {
    var w = ee.Number(sub.map(function (f) { return f.set('w', ee.Number(f.get('score_' + key)).multiply(f.get('a'))); }).aggregate_sum('w'));
    props['score_' + key] = w.divide(area);
    var rw = ee.Number(sub.map(function (f) { return f.set('rw', ee.Number(f.get('raw_score_' + key)).multiply(f.get('a'))); }).aggregate_sum('rw'));
    props['raw_score_' + key] = rw.divide(area);
    props['pct_ge_0_6_' + key] = ee.Number(sub.filter(ee.Filter.gte('score_' + key, 0.6)).aggregate_sum('a')).divide(area).multiply(100);
  });
  return ee.Feature(null, props);
}));
print('LGAs still without soil value after gap fill (named):', inputs.filter(ee.Filter.or(ee.Filter.notNull(['ph']).not(), ee.Filter.notNull(['oc']).not())).aggregate_array('l'));

// ---------------------------------------------- EXPORTS -----------------------------------------------
var inCols = ['id', 'l', 's', 'a', 'soil_fallback', 'rain', 'dry', 'dry_annual', 'dry_clim', 'dry100', 'tmax', 'tmax_cool', 'tmax_wet', 'tmean_cool', 'tmean_wet',
              'slope', 'elev', 'ph', 'oc', 'ph_raw', 'oc_raw', 'isda_ph', 'isda_oc'];
var scoreCols = [];
Object.keys(CROPS).forEach(function (key) {
  scoreCols = scoreCols.concat(['raw_score_' + key, 'score_' + key, 'class_' + key, 'limiting_' + key]);
  FACTORS.forEach(function (k) { scoreCols.push('s_' + key + '_' + k); });
});
// 1. Per-LGA inputs in the column names scripts/apply_export.py expects (tmax -> tmax_hot)
Export.table.toDrive({collection: inputs.map(function (f) { return f.set('tmax_hot', f.get('tmax')); }),
  description: 'agrizone_zonal_all', fileFormat: 'CSV',
  selectors: ['id', 'l', 's', 'rain', 'dry', 'dry100', 'dry_annual', 'dry_clim', 'tmax_hot', 'tmax_cool', 'tmax_wet', 'tmean_cool', 'tmean_wet',
              'slope', 'elev', 'ph', 'oc', 'ph_raw', 'oc_raw', 'isda_ph', 'isda_oc']});
// 2. Cropland-only means (needed by apply_export.py --cropland)
Export.table.toDrive({collection: cropLand.map(function (f) { return f.set('tmax_hot', f.get('tmax')); }),
  description: 'agrizone_zonal_cropland', fileFormat: 'CSV',
  selectors: ['id', 'l', 's', 'rain', 'dry', 'dry100', 'dry_annual', 'dry_clim', 'tmax_hot', 'tmax_cool', 'tmax_wet', 'tmean_cool', 'tmean_wet',
              'slope', 'elev', 'ph', 'oc', 'ph_raw', 'oc_raw', 'isda_ph', 'isda_oc', 'crop_frac']});
// 3. Per-LGA scores, classes, limiting factor and every factor score, for all crops
Export.table.toDrive({collection: scored, description: 'agrizone_lga_scores', fileFormat: 'CSV', selectors: inCols.concat(scoreCols)});
// 4. State x crop summary
Export.table.toDrive({collection: stateTable, description: 'agrizone_state_crop_table', fileFormat: 'CSV',
  selectors: ['state', 'n_lga', 'area_km2'].concat([].concat.apply([], Object.keys(CROPS).map(function (k) { return ['raw_score_' + k, 'score_' + k, 'pct_ge_0_6_' + k]; })))});
