// Google Earth Engine Code Editor: growing-season temperature per LGA
// NOTE: the temperature outputs of this script (MODIS surface temperature) are superseded by 03_air_temp.js and are no longer used by the app.
var lgas = ee.FeatureCollection('FAO/GAUL/2015/level2').filter(ee.Filter.eq('ADM0_NAME','Nigeria'))
  .filter(ee.Filter.neq('ADM2_NAME','Lake chad'));  // water body, not an LGA
var lst = ee.ImageCollection('MODIS/061/MOD11A2').select('LST_Day_1km').filterDate('2015-01-01','2025-01-01');
function conv(i){return i.multiply(0.02).subtract(273.15);}
var cool = conv(lst.filter(ee.Filter.or(ee.Filter.calendarRange(11,12,'month'),ee.Filter.calendarRange(1,2,'month'))).mean()).rename('lst_cool');
var wet = conv(lst.filter(ee.Filter.calendarRange(6,10,'month')).mean()).rename('lst_wet');
Export.table.toDrive({collection:cool.addBands(wet).reduceRegions({collection:lgas,reducer:ee.Reducer.mean(),scale:1000,tileScale:4}),description:'agrizone_lga_season_lst',fileFormat:'CSV',selectors:['ADM1_NAME','ADM2_NAME','lst_cool','lst_wet']});
