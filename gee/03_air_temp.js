// Google Earth Engine Code Editor: AIR temperature per LGA (replaces MODIS surface temperature)
// Source: TerraClimate monthly maximum 2 m air temperature (tmmx), 2015-2024, ~4.6 km pixels.
// Same LGA asset and filter as 01_lga_inputs.js so rows line up.
var lgas = ee.FeatureCollection('FAO/GAUL/2015/level2')
  .filter(ee.Filter.eq('ADM0_NAME', 'Nigeria'))
  .filter(ee.Filter.neq('ADM2_NAME', 'Lake chad'));

var tc = ee.ImageCollection('IDAHO_EPSCOR/TERRACLIMATE')
  .filterDate('2015-01-01', '2025-01-01')
  .select(['tmmx', 'tmmn'])
  .map(function (i) { return i.multiply(0.1).copyProperties(i, ['system:time_start']); }); // already °C after scaling

var tmmx = tc.select('tmmx');

// Replaces `lst`: hottest month of each year (mean daily max), averaged over 2015-2024
var years = ee.List.sequence(2015, 2024);
var tmaxHot = ee.ImageCollection(years.map(function (y) {
  return tmmx.filter(ee.Filter.calendarRange(y, y, 'year')).max();
})).mean().rename('tmax_hot');

// Replaces `lst_cool`: Nov-Feb mean of daily max
var tmaxCool = tmmx.filter(ee.Filter.or(
  ee.Filter.calendarRange(11, 12, 'month'),
  ee.Filter.calendarRange(1, 2, 'month'))).mean().rename('tmax_cool');

// Replaces `lst_wet`: Jun-Oct mean of daily max
var tmaxWet = tmmx.filter(ee.Filter.calendarRange(6, 10, 'month')).mean().rename('tmax_wet');

// For reference: annual mean air temperature
var tmeanAnn = tc.map(function (i) { return i.reduce(ee.Reducer.mean()); }).mean().rename('tmean_ann');

var img = tmaxHot.addBands([tmaxCool, tmaxWet, tmeanAnn]);

var out = img.reduceRegions({
  collection: lgas,
  reducer: ee.Reducer.mean(),
  scale: 4638,      // native TerraClimate pixel size
  tileScale: 4
});

// Sanity checks in the Console
print('LGAs:', out.size());                                         // expect 774
print('Null tmax_hot:', out.filter(ee.Filter.notNull(['tmax_hot']).not()).size()); // expect 0
print('Kano sample:', out.filter(ee.Filter.eq('ADM1_NAME', 'Kano')).limit(3));
print('Ondo sample:', out.filter(ee.Filter.eq('ADM1_NAME', 'Ondo')).limit(3));

Export.table.toDrive({
  collection: out,
  description: 'agrizone_lga_air_temp',
  fileFormat: 'CSV',
  selectors: ['ADM1_NAME', 'ADM2_NAME', 'tmax_hot', 'tmax_cool', 'tmax_wet', 'tmean_ann']
});
