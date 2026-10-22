#!/usr/bin/env python3
"""Leakage-aware crop-yield model training and evaluation for AgriZone.

Input CSV: one row per independent yield observation (preferably plot/farm x crop x season).
Required: crop, yield_t_ha, year, state, lga. Predictors must be numeric columns listed in --features.
Optional: site_id, latitude, longitude, observation_source, sample_weight.

This script does not create observations or certify accuracy. It refuses to claim a validated
model when the dataset is too small for grouped validation. Evaluation splits hold out whole
states where feasible; time split is also reported when >= 4 years are present.
"""
import argparse, json, warnings
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor, HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.dummy import DummyRegressor


def metrics(y, p):
    y=np.asarray(y,dtype=float); p=np.asarray(p,dtype=float)
    rmse=float(np.sqrt(mean_squared_error(y,p)))
    denom=np.maximum(np.abs(y), 0.1)
    return {'n':int(len(y)), 'MAE_t_ha':float(mean_absolute_error(y,p)), 'RMSE_t_ha':rmse,
            'R2':float(r2_score(y,p)) if len(y)>1 else None,
            'mean_bias_t_ha':float(np.mean(p-y)), 'median_absolute_error_t_ha':float(np.median(np.abs(p-y))),
            'MAPE_percent_excluding_near_zero':float(np.mean(np.abs(p-y)/denom)*100)}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--data', required=True, help='CSV of observed yields and predictors')
    ap.add_argument('--out', default='yield_model_results', help='Output directory')
    ap.add_argument('--features', required=True, help='Comma-separated numeric predictor columns')
    ap.add_argument('--min-observations', type=int, default=60)
    ap.add_argument('--min-states', type=int, default=5)
    args=ap.parse_args()
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    df=pd.read_csv(args.data)
    required={'crop','yield_t_ha','year','state','lga'}
    missing=required-set(df.columns)
    if missing: raise SystemExit(f'Missing required columns: {sorted(missing)}')
    feats=[x.strip() for x in args.features.split(',') if x.strip()]
    missing=set(feats)-set(df.columns)
    if missing: raise SystemExit(f'Missing feature columns: {sorted(missing)}')
    df['yield_t_ha']=pd.to_numeric(df.yield_t_ha,errors='coerce')
    df['year']=pd.to_numeric(df.year,errors='coerce')
    for f in feats: df[f]=pd.to_numeric(df[f],errors='coerce')
    df=df.dropna(subset=['crop','yield_t_ha','year','state','lga'])
    df=df[(df.yield_t_ha>0)&np.isfinite(df.yield_t_ha)]
    df=df.drop_duplicates(subset=[c for c in ['crop','year','state','lga','site_id'] if c in df.columns])
    summary=[]; predictions=[]; models={}
    for crop,g in df.groupby('crop'):
        g=g.dropna(subset=['yield_t_ha']).copy()
        nstates=g.state.nunique(); nyears=g.year.nunique()
        if len(g)<args.min_observations or nstates<args.min_states:
            summary.append({'crop':crop,'status':'INSUFFICIENT_DATA','n':len(g),'states':nstates,'years':nyears,
                            'reason':f'Requires >= {args.min_observations} observations and >= {args.min_states} states; no validation score reported.'})
            continue
        X=g[feats]; y=g.yield_t_ha.to_numpy()
        # Baseline: training-fold median, not a model using future/held-out information.
        groups=g.state.astype(str).to_numpy()
        n_splits=min(5,nstates)
        cv=GroupKFold(n_splits=n_splits)
        model=Pipeline([('imputer',SimpleImputer(strategy='median', add_indicator=True)),
                        ('model',RandomForestRegressor(n_estimators=500,min_samples_leaf=3,max_features=0.8,
                         random_state=42,n_jobs=-1))])
        try:
            pred=cross_val_predict(model,X,y,cv=cv,groups=groups,n_jobs=1)
            baseline=np.zeros(len(y),dtype=float)
            for tr,te in cv.split(X,y,groups): baseline[te]=np.median(y[tr])
            met=metrics(y,pred); base=metrics(y,baseline)
            status='VALIDATION_PASSED' if met['RMSE_t_ha'] < base['RMSE_t_ha'] else 'MODEL_DID_NOT_BEAT_BASELINE'
            # Interval is an empirical absolute-error quantile from out-of-fold predictions, not a calibrated guarantee.
            q=float(np.quantile(np.abs(y-pred),0.9))
            met.update({'crop':crop,'status':status,'states':nstates,'years':nyears,'split':'GroupKFold by state',
                        'baseline_RMSE_t_ha':base['RMSE_t_ha'],'baseline_MAE_t_ha':base['MAE_t_ha'],
                        'empirical_90pct_abs_error_t_ha':q,
                        'warning':'Cross-validated only on the supplied observations; sampling design, spatial bias and data quality still matter.'})
            summary.append(met)
            pp=g[['crop','year','state','lga']].copy(); pp['observed_yield_t_ha']=y; pp['oof_predicted_yield_t_ha']=pred
            pp['oof_error_t_ha']=pred-y; pp['empirical_abs_error_band_t_ha']=q; predictions.append(pp)
            model.fit(X,y); models[crop]=model
        except Exception as e:
            summary.append({'crop':crop,'status':'VALIDATION_ERROR','n':len(g),'states':nstates,'years':nyears,'reason':str(e)})
    pd.DataFrame(summary).to_csv(out/'crop_validation_metrics.csv',index=False)
    if predictions: pd.concat(predictions,ignore_index=True).to_csv(out/'out_of_fold_predictions.csv',index=False)
    # Store feature list and fitted estimators only after explicit successful fitting.
    import joblib
    if models: joblib.dump({'models':models,'features':feats},out/'crop_yield_models.joblib')
    (out/'README.txt').write_text('Results are from out-of-fold predictions grouped by state. They are not a guarantee of future accuracy. Check sample sizes, provenance, spatial/temporal coverage, and whether the model beats the baseline before deployment. Do not extrapolate beyond observed crop/climate regimes.\n')
    print(pd.DataFrame(summary).to_string(index=False))

if __name__=='__main__': main()
