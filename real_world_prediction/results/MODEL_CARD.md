# Model card: CropLocus exploratory yield models

- **Purpose:** research prototype to assess whether CropLocus environmental summaries can predict observed Nigerian crop yields.
- **Status:** exploratory only; not approved for agricultural recommendations, credit/insurance decisions, or farm planning.
- **Targets:** maize, sorghum, rice, cassava.
- **Data:** GROW-Africa LSMS survey observations from 2010, 2012, 2015 and 2018, matched to CropLocus LGA environmental summaries.
- **Predictors:** rainfall, dry months, hot/cool/wet season maximum temperature, soil pH, organic carbon and slope.
- **Validation:** grouped holdout by assigned state; separate exploratory latest-year diagnostic.
- **Observed performance:** negative R² for every crop; MAE worse than median baseline for every crop. RMSE is only slightly better than the baseline.
- **Known risks:** 5 km spatial precision, approximate polygon matching, temporal mismatch between survey years and 2015–2024 climate summaries, unmodelled survey design, and aggregate LGA predictors.
- **Unsupported uses:** precise farm-level yield forecasts, future-season forecasting, claims of suitability or yield performance for crops without observations, and claims of validated accuracy across all Nigerian LGAs.
- **Responsible presentation:** label all predictions experimental, show uncertainty and geographic coverage, and do not present outputs as validated until further independent testing improves results.
