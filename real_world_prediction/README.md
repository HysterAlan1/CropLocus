# Real-world prediction module

The parent CropLocus project estimates relative environmental suitability. This folder adds a leakage-aware starter workflow for a separate yield model. Actual validation requires real observed yields with location, crop and year metadata.

See `DATA_SOURCES_AND_PROTOCOL.md` for data sources, required columns, validation rules and limitations. Run `python train_validate_yield_model.py --data your_observations.csv --features rainfall,temp_max,soil_ph,organic_carbon,ndvi --out results` after replacing feature names with columns present in your verified dataset.

The script is not a claim that the model is already trained or validated. It will label insufficient datasets as such and compares cross-validated predictions against a training-fold median baseline.
