# CropLocus

**Crop suitability mapping for Nigeria**

CropLocus maps environmental suitability for eight crops across Nigeria's local government areas (LGAs). Select a state or LGA to explore the map, suitability scores and the factors used in the assessment.

## Open the map

Open `index.html` in a modern web browser. The map and its main data are included in this folder.

## Project folders

- `index.html` — interactive map and interface
- `build/` — map data, boundaries and browser libraries
- `data/` — environmental inputs, crop scores and reference tables
- `gee/` — Google Earth Engine scripts used to prepare spatial inputs
- `scripts/` — data preparation and checking scripts
- `real_world_prediction/` — experimental crop-yield modelling and evaluation materials

## Environmental factors

The suitability assessment uses rainfall, dry-season conditions, temperature, soil pH, soil organic carbon and slope. Scores indicate environmental suitability; they should not be interpreted as guaranteed farm yields.

## Validation notes

The project includes exploratory checks against available crop observations. These checks do not establish reliable yield prediction for every crop or LGA. Review `VALIDATION_AND_CALIBRATION.md` and `real_world_prediction/results/FINAL_VALIDATION_REPORT.md` for the methods, results and limitations.

## Reproducibility

The scripts and input tables are retained so the workflow can be reviewed and updated. Some data preparation steps require Python packages or Google Earth Engine access.
