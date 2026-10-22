# CropLocus v3: scoring revision and independent validation

## What changed

- Kept the crop-specific factor-response curves and transparent expert-rule weights: rainfall 0.32, dry months 0.15, crop-relevant maximum temperature 0.25, soil pH 0.13, organic carbon 0.05, slope 0.10.
- Added a **limiting-factor adjustment** to reduce compensation: `adjusted score = raw weighted index × sqrt(minimum factor membership)`. The raw index remains available in `raw_score_<crop>` columns; the map shows the adjusted score.
- Revised operational class bands for the adjusted score: High ≥0.80; Moderate 0.60–<0.80; Marginal 0.40–<0.60; Unsuitable <0.40.
- Synced the browser app, Earth Engine scoring scripts, Python scoring helpers, all-LGA exports, state summaries, and validation code.
- Updated `build/data.js` to use full-precision environmental inputs so the dashboard and CSV exports can reproduce the same results.
- Recomputed scores and class labels for all 774 LGAs, and area-weighted state/FCT summaries.

This is a **conservative rule-based revision**, not a statistically fitted calibration. The adjusted formula and class boundaries are explicit modelling choices. They reduce over-compensation by a weak factor but are not claimed to be universally more predictive of yield.

## Revised score distribution

| Crop | Unsuitable | Marginal | Moderate | High | Mean adjusted score |
|---|---:|---:|---:|---:|---:|
| Cocoa | 385 | 76 | 186 | 127 | 0.402 |
| Wheat | 492 | 152 | 130 | 0 | 0.264 |
| Cassava | 159 | 106 | 134 | 375 | 0.691 |
| Rice | 211 | 73 | 90 | 400 | 0.639 |
| Sorghum | 306 | 70 | 75 | 323 | 0.537 |
| Oil palm | 573 | 75 | 63 | 63 | 0.201 |
| Maize | 294 | 103 | 148 | 229 | 0.540 |
| Tomato | 148 | 100 | 247 | 279 | 0.646 |

The changed distributions are a sensitivity signal, not proof of better field performance. In particular, wheat and oil palm scores are conservative under the current factor ranges and deserve agronomist review.

## Independent external check: official state yields

The project now includes state-level yield observations from the NAERLS/FMAFS **2024 Wet Season Agricultural Performance in Nigeria** report, Tables 12.1 (rice), 12.2 (maize), 12.3 (sorghum), 12.10 (cassava), and 12.14 (tomato). These are compared against area-weighted state means of the LGA scores. The report is an independent data source, but this is not a clean yield-prediction test: the model's climate summaries include 2015–2024, and observed yield also depends on varieties, inputs, irrigation, pests, markets, crop area and reporting quality.

| Crop | States | Raw index Spearman ρ | Adjusted score Spearman ρ | Interpretation |
|---|---:|---:|---:|---|
| Maize | 37 | 0.445 | 0.455 | Moderate positive rank association |
| Cassava | 34 | 0.431 | 0.401 | Moderate positive association; sensitive to one suspect official yield value |
| Tomato | 34 | 0.393 | 0.265 | Weak-to-moderate association; adjustment reduces correlation |
| Rice | 37 | 0.243 | 0.253 | Weak association; confidence interval includes zero |
| Sorghum | 22 | -0.135 | -0.137 | No positive association in the available state subset |

Bootstrap intervals (500 resamples) are in `scripts/yield_validation_results.csv`; they are descriptive state-resampling intervals and do not correct for spatial dependence. The cassava table reports Ebonyi yield at 0.04 MT/ha, an apparent outlier compared with neighbouring states and the table's area/production values; excluding Ebonyi increases Spearman ρ to 0.486 for the raw index and 0.458 for the adjusted score. Treat that crop/state benchmark as questionable until checked against the source or a second official dataset.

The result is mixed. The adjusted score modestly improves the yield rank association for maize and rice, but lowers it for cassava and tomato and does not improve sorghum. **Do not describe the model as yield-validated or fully calibrated.** The independent check has identified where more work is needed, rather than proving that the adjustment improves every crop.

## GBIF occurrence/background check

Strictly filtered GBIF occurrence records were mapped to LGA polygons and compared with unoccupied LGAs. This is an ecological presence/background sanity check, not a crop-yield test; absence of a GBIF record is not evidence that a crop cannot grow there. Results use the adjusted scores:

| Crop | Unique records | Occupied LGAs | AUC | 95% bootstrap interval | Status |
|---|---:|---:|---:|---:|---|
| Cocoa | 50 | 30 | 0.831 | 0.764–0.887 | Indicative |
| Cassava | 175 | 117 | 0.626 | 0.573–0.678 | Indicative |
| Rice | 170 | 80 | 0.582 | 0.505–0.654 | Weak |
| Sorghum | 596 | 278 | 0.752 | 0.715–0.783 | Indicative |
| Oil palm | 259 | 74 | 0.855 | 0.814–0.891 | Indicative |
| Maize | 28 | 24 | 0.656 | 0.583–0.728 | Low n |
| Tomato | 25 | 21 | 0.711 | 0.637–0.789 | Low n |
| Wheat | 0 | 0 | Not available | Not available | No records survive strict filter |

These intervals bootstrap occupied and unoccupied LGAs but are not spatially blocked. GBIF sampling bias, crop-name matching, record quality and LGA-level aggregation remain limitations.

## Recommended interpretation

- The score is a **relative environmental screening index** for the included factors, not a probability, yield estimate, or farming recommendation.
- Tomato is currently represented as irrigated tomato; irrigation availability is not mapped. Rainfed lowland rice is the rice system assumed.
- State-level production/yield is used as an external consistency check only. Stronger calibration requires LGA/plot-level yield observations, crop-specific calendars, irrigation/cropland masks, and spatially held-out validation data.
- Do not fit weights to the same yields later reported as independent validation. If weights are calibrated later, reserve separate states/years for testing.

## Reproducible outputs

- `data/gee_lga_scores_v3.csv`: raw index, adjusted score, factor memberships and classes for 774 LGAs.
- `data/gee_state_crop_table_v3.csv`: area-weighted state/FCT summaries.
- `data/model_diagnostics_v3.csv`: revised score distributions.
- `data/official_state_yields_2024.csv`: independent official yield observations and source table identifiers.
- `scripts/validate_yields.py`: state-yield rank-correlation check.
- `scripts/yield_validation_results.csv`: raw vs adjusted score comparisons.
- `scripts/validation_results_strict.csv`: strict GBIF presence/background results.
- `scripts/validate.py`: repeatable GBIF validation.

## Source

NAERLS/FMAFS (2024), *2024 Wet Season Agricultural Performance in Nigeria: National Report*, Tables 12.1, 12.2, 12.3, 12.10 and 12.14: https://naerls.gov.ng/wp-content/uploads/2025/04/Agricultural-Performance-Survey-of-2024-Wet-Season-in-Nigeria.pdf
