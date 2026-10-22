// Google Earth Engine Code Editor: annual inputs per LGA
// NOTE: the temperature outputs of this script (MODIS surface temperature) are superseded by 03_air_temp.js and are no longer used by the app.
var lgas = ee.FeatureCollection('FAO/GAUL/2015/level2').filter(ee.Filter.eq('ADM0_NAME','Nigeria'))
  .filter(ee.Filter.neq('ADM2_NAME','Lake chad'));  // water body, not an LGA
var chirps = ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY');
var years = ee.List.sequence(2015, 2024);
var monthly = ee.ImageCollection(ee.List.sequence(1,12).map(function(m){
  return ee.ImageCollection(years.map(function(y){
    return chirps.filter(ee.Filter.calendarRange(y,y,'year')).filter(ee.Filter.calendarRange(m,m,'month')).sum();
  })).mean();
}));
var rain = monthly.sum().rename('rain');
var dry = monthly.map(function(i){return i.lt(50);}).sum().rename('dry');
var lst = ee.ImageCollection('MODIS/061/MOD11A2').filterDate('2015-01-01','2025-01-01').select('LST_Day_1km')
  .reduce(ee.Reducer.percentile([95])).multiply(0.02).subtract(273.15).rename('lst');
var dem = ee.Image('NASA/NASADEM_HGT/001').select('elevation');
var slope = ee.Terrain.slope(dem).multiply(Math.PI/180).tan().multiply(100).rename('slope');
var ph = ee.Image('projects/soilgrids-isric/phh2o_mean').select(['phh2o_0-5cm_mean','phh2o_5-15cm_mean','phh2o_15-30cm_mean']).reduce(ee.Reducer.mean()).divide(10).rename('ph');
var oc = ee.Image('projects/soilgrids-isric/soc_mean').select(['soc_0-5cm_mean','soc_5-15cm_mean','soc_15-30cm_mean']).reduce(ee.Reducer.mean()).divide(10).rename('oc');
var out = rain.addBands([dry,lst,slope,dem.rename('elev'),ph,oc]).reduceRegions({collection:lgas,reducer:ee.Reducer.mean(),scale:1000,tileScale:4});
Export.table.toDrive({collection:out,description:'agrizone_lga_inputs',fileFormat:'CSV',selectors:['ADM1_NAME','ADM2_NAME','rain','dry','lst','ph','oc','slope','elev']});
