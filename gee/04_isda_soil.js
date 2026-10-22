// Google Earth Engine Code Editor: iSDAsoil pH and organic carbon per LGA, 0-30 cm, for checking SoilGrids.
// iSDAsoil (30 m, Africa only) was trained on African field samples. Datasets and scaling, from the Earth Engine catalog:
//   ISDASOIL/Africa/v1/ph              bands mean_0_20, mean_20_50   back-transform: x / 10
//   ISDASOIL/Africa/v1/carbon_organic  bands mean_0_20, mean_20_50   back-transform: exp(x / 10) - 1   (g/kg)
// Depths are combined to 0-30 cm as 20 cm of the top layer + 10 cm of the 20-50 layer, matching the SoilGrids
// 0-5, 5-15 and 15-30 cm average used in 01_lga_inputs.js.
var lgas = ee.FeatureCollection('FAO/GAUL/2015/level2').filter(ee.Filter.eq('ADM0_NAME', 'Nigeria'))
  .filter(ee.Filter.neq('ADM2_NAME', 'Lake chad'));
var phRaw = ee.Image('ISDASOIL/Africa/v1/ph');
var ph = phRaw.select('mean_0_20').multiply(2).add(phRaw.select('mean_20_50')).divide(3).divide(10).rename('isda_ph');
var ocRaw = ee.Image('ISDASOIL/Africa/v1/carbon_organic');
function bt(b) { return ocRaw.select(b).divide(10).exp().subtract(1); }
var oc = bt('mean_0_20').multiply(2).add(bt('mean_20_50')).divide(3).rename('isda_oc');   // average after back-transforming
var img = ph.addBands(oc);
var out = img.reduceRegions({collection: lgas, reducer: ee.Reducer.mean(), scale: 250, tileScale: 8});
print('LGAs:', out.size());                                                                  // expect 774
print('LGAs with no iSDA pH:', out.filter(ee.Filter.notNull(['isda_ph']).not()).size());     // blanks mean iSDA has no data there
print('LGAs with no iSDA organic carbon:', out.filter(ee.Filter.notNull(['isda_oc']).not()).size());
print('Kano sample:', out.filter(ee.Filter.eq('ADM1_NAME', 'Kano')).limit(2));
Export.table.toDrive({
  collection: out, description: 'agrizone_lga_isda_soil', fileFormat: 'CSV',
  selectors: ['ADM1_NAME', 'ADM2_NAME', 'isda_ph', 'isda_oc']
});
