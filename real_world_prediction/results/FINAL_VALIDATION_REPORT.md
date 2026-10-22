# CropLocus — Real-world yield validation report

**Status: exploratory validation completed; not deployment-ready for farm-level yield advice.**

## Executive summary

CropLocus was joined to Nigerian crop observations in the supplied GROW-Africa LSMS survey workbook. The analysis used GPS-based yield (`YieldUsingGPS_ton_ha_`) and the eight LGA-level environmental predictors embedded in the supplied CropLocus project: annual rainfall, dry-month count, hot-season maximum temperature, soil pH, organic carbon, slope, cool-season maximum temperature and wet-season maximum temperature.

The workbook has 195,152 total records and 12,361 Nigeria records. The target crops in this analysis had 5,845 observations retained after basic screening and crop-specific 99.5th-percentile review. Tomato was not present in the Nigerian records. The spatial join uses GPS points against CropLocus LGA polygons; when a point was not inside a polygon, the nearest polygon was assigned. The source reports spatial precision around 5 km for many records, so these LGA assignments are approximate.

## Spatial generalization test

Predictions were generated with 5-fold `GroupKFold` (or fewer folds where needed), holding out entire assigned states. The baseline is the median yield in each training fold. All metrics are in tonnes/hectare.

| Crop | Observations | States | MAE | RMSE | R² | Baseline MAE | Baseline RMSE |
|---|---:|---:|---:|---:|---:|---:|---:|
| Cassava | 655 | 28 | 5.938 | 8.633 | -0.044 | 5.144 | 9.032 |
| Maize | 2,610 | 36 | 1.414 | 1.903 | -0.100 | 1.229 | 1.925 |
| Rice | 596 | 26 | 1.810 | 2.358 | -0.078 | 1.662 | 2.371 |
| Sorghum | 1,984 | 21 | 1.033 | 1.276 | -0.123 | 0.891 | 1.318 |

### Interpretation

The random-forest model slightly lowers RMSE versus the median baseline for each crop, but it has **higher MAE** for every crop and **negative R²** for every crop. This means the models do not explain out-of-state yield variation well enough to support reliable yield advice. The small RMSE differences should not be described as strong predictive success.

## Temporal holdout diagnostic

The latest available year (2018) was held out, with earlier available years used for training. Results are in `temporal_holdout_diagnostic.csv`. These results are also exploratory because the environmental climate features are 2015–2024 summaries, not climate covariates matched to the 2010, 2012, 2015 and 2018 survey seasons. The temporal test therefore cannot be interpreted as a clean operational forecast test.

## Data handling and limitations

- Yield field: `YieldUsingGPS_ton_ha_`, based on GPS-measured plot area.
- Records above the crop-specific 99.5th percentile were flagged and excluded from the main fit, but preserved in the audit file. This is a screening decision, not proof of error.
- Survey points may be spatially blurred; polygon-based LGA assignment is approximate.
- Crop-cut/household survey data can have complex sampling and reporting errors; the analysis does not yet apply survey weights.
- Several plot observations can share households, coordinates or local conditions. State-grouped cross-validation reduces broad geographic leakage but does not fully remove within-state spatial dependence.
- Predictors are LGA means and climate summaries, not plot-specific and year-specific environmental conditions.
- This validates only maize, sorghum, rice and cassava with the available Nigeria sample. It does not validate all eight crops or all 774 LGAs.
- No claim is made that this model is perfect or production-ready.

## Recommended next work before deployment

1. Obtain year-specific climate/weather predictors for each survey season and, ideally, plot-level soil and terrain values.
2. Reconcile the source survey sampling design and use appropriate survey weights where supported.
3. Use spatial block cross-validation within states and repeated grouped splits; retain a final untouched geographic test set.
4. Evaluate additional baselines and models, calibrate prediction intervals on held-out data, and report errors by state, agroecological zone and yield range.
5. Obtain later-year independent yield data for a genuinely forward-in-time test.
6. Keep yield prediction clearly separate from the existing environmental suitability score in the user interface until validation is satisfactory.

## Included outputs

- `spatial_validation_metrics.csv`: out-of-state cross-validation metrics and baseline comparison.
- `temporal_holdout_diagnostic.csv`: exploratory 2018 holdout results.
- `out_of_fold_predictions.csv`: observed and held-out predicted yields.
- `nigeria_yield_observation_audit.csv`: matched observations, predictors and exclusion flags.
- `exploratory_crop_yield_models.joblib`: fitted exploratory models and feature names.
- `data_audit.txt`: key processing decisions.
