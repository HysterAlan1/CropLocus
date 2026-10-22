# CropLocus real-world yield prediction: evidence and validation protocol

## Important limitation
No crop-yield model is “perfect.” The existing CropLocus score is an environmental suitability index, not a yield forecast. The current state-level 2024 comparison is an external consistency check and does not validate LGA-level prediction accuracy. Do not report a yield in t/ha until an actual-yield model has been trained and passed held-out validation.

## Real-world datasets to acquire
1. **Nigeria National Agricultural Sample Survey (NASS) 2023**: NBS/FAO survey includes crop, harvest, location/state/LGA and household/plot variables. Public access and dataset documentation: https://microdata.nigerianstat.gov.ng/index.php/catalog/173 and https://www.fao.org/in-action/agrisurvey/access-to-data/nigeria/en . Respect the survey weights, design and anonymization; inspect variable definitions before deriving yield.
2. **GROW-Africa v2.0**: 535,844 georeferenced African yield observations across 25 crops, with mixed observation scales. Use it to discover/augment records only after filtering to Nigeria, checking crop/year/location, units, source, and observation scale. It is not automatically representative of every Nigerian LGA. https://zenodo.org/records/16544448 (DOI: 10.5281/zenodo.16544448).
3. **FAOSTAT national annual yields**: useful for national trend sanity checks, not LGA model training. Coverage 1961–2024. https://data.fao.org/catalog/iso/d24a448b-3b62-4c09-8c1d-4a39bb599876 .
4. **NAERLS/FMAFS 2024 wet-season report**: use the crop-specific state tables already referenced by the project as an independent state-level consistency check, not as a substitute for farm/LGA observations. https://naerls.gov.ng/wp-content/uploads/2025/04/Agricultural-Performance-Survey-of-2024-Wet-Season-in-Nigeria.pdf .

## Required data structure
One row per independent observed crop x site/plot x season. Required columns: `crop,yield_t_ha,year,state,lga`; add `site_id,latitude,longitude,season,harvested_area_ha,production_t,source,observation_scale,sampling_weight` where available. Calculate yield as production / harvested area only if both are measured in compatible units and same crop, season and geography. Keep yield moisture/basis and crop form consistent (e.g. paddy vs milled rice; fresh cassava root vs dry matter).

## Predictors to align to crop season
- Seasonal rainfall, dry-spell length and temperature (not annual averages alone)
- Soil texture, pH, organic carbon and drainage/rooting constraints
- Vegetation/phenology (e.g. NDVI/EVI) and surface temperature from satellite data
- Crop calendar, irrigation/rainfed status, variety, planting date, fertilizer and other management when available
- Cropland mask and crop-specific suitable geography

All predictors must be measured using only information available at forecast time. Never use yield-derived or post-harvest data as predictors.

## Validation protocol
- Deduplicate observations and retain source/quality flags; inspect outliers and unit consistency before modelling.
- Compare against a training-fold median and a historical yield baseline.
- Use grouped holdout by state or spatial blocks, plus forward-in-time holdout by year. Random row splits alone leak location/season patterns and are insufficient.
- Report MAE and RMSE in t/ha, bias, R² (with caveats), number of observations/states/years, crop-specific results and baseline comparisons. Report error ranges and where model is extrapolating.
- Keep a final untouched test set. If any parameters are tuned on a validation set, do not reuse that set as final independent evidence.
- Do not deploy a crop model unless it beats the baseline on held-out data, has reasonable errors for the intended decision, and has adequate spatial/temporal coverage. Have an agronomist review crop-specific results.

## Included starter script
`train_validate_yield_model.py` performs crop-specific Random Forest modelling, median imputation inside each training fold, grouped cross-validation by state, out-of-fold predictions, error metrics, and a fold-safe median baseline. It requires actual observations; it does not fabricate data or imply validation when the input is insufficient. The empirical 90th percentile absolute error is descriptive and not a formal calibrated prediction interval.
