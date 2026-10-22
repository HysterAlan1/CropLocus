import re,json, pandas as pd, numpy as np, os, warnings
from shapely.geometry import shape, Point
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from pathlib import Path
root=Path('/mnt/data/finalwork/agrizone'); out=root/'real_world_prediction'/'results'; out.mkdir(parents=True,exist_ok=True)
# parse LGA GeoJSON embedded in data.js
s=(root/'build/data.js').read_text()
m=re.search(r'const const LGA=(\{"type":"FeatureCollection".*?\});const STATES=',s)
if not m: raise RuntimeError('Could not parse embedded LGA feature collection')
geo=json.loads(m.group(1)[:-1] if m.group(1).endswith(';') else m.group(1))
features=[]
for f in geo['features']:
 p=f['properties']; vals=p.get('v',[])
 features.append({'lga':p['l'],'state':p['s'],'rain':vals[0] if len(vals)>0 else np.nan,'dry_months':vals[1] if len(vals)>1 else np.nan,'tmax_hot':vals[2] if len(vals)>2 else np.nan,'soil_ph':vals[3] if len(vals)>3 else np.nan,'organic_carbon':vals[4] if len(vals)>4 else np.nan,'slope':vals[5] if len(vals)>5 else np.nan,'tmax_cool':vals[6] if len(vals)>6 else np.nan,'tmax_wet':vals[7] if len(vals)>7 else np.nan,'geom':shape(f['geometry'])})
# read converted csv
p='/mnt/data/finalwork/convert/GROW-Africa_LSMS_survey.csv'; df=pd.read_csv(p,low_memory=False)
ng=df[df.Country.eq('Nigeria')].copy()
ng['lat']=pd.to_numeric(ng.GPS_lat,errors='coerce'); ng['lon']=pd.to_numeric(ng.GPS_lon,errors='coerce')
# assign point to polygon; if not within due precision/boundaries, nearest centroid
from shapely.ops import nearest_points
from shapely.strtree import STRtree
_geoms=[f['geom'] for f in features]; _tree=STRtree(_geoms); _geom_idx={id(g):i for i,g in enumerate(_geoms)}
assigned=[]
for lat,lon in zip(ng.lat,ng.lon):
 pt=Point(lon,lat); hit=None
 cand=_tree.query(pt)
 for idx in cand:
  gg=_geoms[int(idx)]
  if gg.covers(pt): hit=features[int(idx)]; break
 if hit is None:
  # nearest polygon centroid; coordinates are spatially blurred at roughly 5km so this is approximate
  idx=int(_tree.nearest(pt)); hit=features[idx]
 assigned.append(hit)
ng['assigned_state']=[x['state'] for x in assigned]; ng['assigned_lga']=[x['lga'] for x in assigned]
for k in ['rain','dry_months','tmax_hot','soil_ph','organic_carbon','slope','tmax_cool','tmax_wet']:
 ng[k]=[x[k] for x in assigned]
ng['year']=pd.to_numeric(ng.AgYearStart,errors='coerce')
ng['yield_t_ha']=pd.to_numeric(ng['YieldUsingGPS_ton_ha_'],errors='coerce')
ng['crop_clean']=ng.Crop.astype(str).str.strip().str.lower()
# crops and plausible conservative screening; use observed GPS-area yield, trim only nonpositive and >99.5th percentile per crop, retain audit
crops=['maize','sorghum','rice','cassava']
ng['yield_flag']='included_candidate'
ng.loc[~np.isfinite(ng.yield_t_ha) | (ng.yield_t_ha<=0),'yield_flag']='missing_or_nonpositive_yield'
ng.loc[ng['SpatialPrecision_km_'].astype(str).str.lower().isin(['nan','none','']), 'yield_flag']='missing_spatial_precision'
selected=ng[ng.crop_clean.isin(crops)].copy()
# audit outliers with crop-specific 99.5 percentile, do not silently drop: mark and exclude from main score
for c,g in selected.groupby('crop_clean'):
 q=g.loc[(g.yield_t_ha>0)&np.isfinite(g.yield_t_ha),'yield_t_ha'].quantile(.995)
 selected.loc[(selected.crop_clean==c)&(selected.yield_t_ha>q),'yield_flag']='above_crop_p99_5_review'
valid=selected[(selected.yield_t_ha>0)&np.isfinite(selected.yield_t_ha)&(selected.yield_t_ha.notna())&(selected.yield_t_ha<=selected.groupby('crop_clean').yield_t_ha.transform(lambda s:s.quantile(.995)))].copy()
# output matched dataset & audit
cols=['Country','Source2','AgYearStart','AgYearEnd','Crop','GPS_lat','GPS_lon','SpatialPrecision_km_','hhid','plotid','Prod_kg_','GPSArea_ha_','YieldUsingGPS_ton_ha_','yield_flag','assigned_state','assigned_lga','rain','dry_months','tmax_hot','soil_ph','organic_carbon','slope','tmax_cool','tmax_wet']
selected[cols].to_csv(out/'nigeria_yield_observation_audit.csv',index=False)
features_cols=['rain','dry_months','tmax_hot','soil_ph','organic_carbon','slope','tmax_cool','tmax_wet']
summary=[]; preds=[]; import joblib
models={}
for crop,g in valid.groupby('crop_clean'):
 g=g.copy(); g['state_group']=g.assigned_state.astype(str)
 # remove incomplete feature rows? imputer handles features; ensure enough unique states
 n=len(g); ns=g.state_group.nunique(); ny=g.year.nunique()
 if n<60 or ns<5:
  summary.append({'crop':crop,'n':n,'states':ns,'years':ny,'status':'INSUFFICIENT_FOR_SPATIAL_CV'}); continue
 X=g[features_cols]; y=g.yield_t_ha.to_numpy(); groups=g.state_group.to_numpy(); cv=GroupKFold(n_splits=min(5,ns))
 model=make_pipeline(SimpleImputer(strategy='median',add_indicator=True),RandomForestRegressor(n_estimators=120,min_samples_leaf=4,max_features=.8,random_state=42,n_jobs=2))
 pred=cross_val_predict(model,X,y,cv=cv,groups=groups,n_jobs=1)
 base=np.empty(len(y));
 for tr,te in cv.split(X,y,groups): base[te]=np.median(y[tr])
 def met(y,p): return {'MAE_t_ha':float(mean_absolute_error(y,p)),'RMSE_t_ha':float(np.sqrt(mean_squared_error(y,p))),'R2':float(r2_score(y,p))}
 m=met(y,pred); b=met(y,base)
 status='BEATS_MEDIAN_BASELINE_RMSE' if m['RMSE_t_ha']<b['RMSE_t_ha'] else 'DOES_NOT_BEAT_MEDIAN_BASELINE_RMSE'
 summary.append({'crop':crop,'n':n,'states':ns,'years':ny,'status':status,'split':'GroupKFold by assigned state','predictors':','.join(features_cols),**m,'baseline_MAE_t_ha':b['MAE_t_ha'],'baseline_RMSE_t_ha':b['RMSE_t_ha'],'baseline_R2':b['R2'],'mean_bias_t_ha':float(np.mean(pred-y)),'p90_abs_error_t_ha':float(np.quantile(np.abs(pred-y),.9)),'notes':'Exploratory validation only; survey GPS precision, historical yield vs 2015-2024 climate mismatch, sample design, and state-level grouping limit interpretation.'})
 pp=g[['Crop','AgYearStart','assigned_state','assigned_lga','GPS_lat','GPS_lon','SpatialPrecision_km_','yield_t_ha']].copy(); pp['oof_predicted_yield_t_ha']=pred; pp['oof_error_t_ha']=pred-y; pp['crop_clean']=crop; preds.append(pp)
 model.fit(X,y); models[crop]=model
pd.DataFrame(summary).to_csv(out/'spatial_validation_metrics.csv',index=False)
if preds: pd.concat(preds,ignore_index=True).to_csv(out/'out_of_fold_predictions.csv',index=False)
if models: joblib.dump({'models':models,'features':features_cols,'crops':list(models)},out/'exploratory_crop_yield_models.joblib')
# year-based holdout diagnostic train earlier years test latest year; only if at least 3 years and train has all
future=[]
for crop,g in valid.groupby('crop_clean'):
 years=sorted(g.year.dropna().unique())
 if len(years)<3: future.append({'crop':crop,'status':'NOT_TESTED','reason':'Fewer than three observed years'}); continue
 testyear=years[-1]; tr=g[g.year<testyear]; te=g[g.year==testyear]
 if len(tr)<40 or len(te)<20:
  future.append({'crop':crop,'status':'NOT_TESTED','test_year':testyear,'n_train':len(tr),'n_test':len(te),'reason':'Insufficient train/test records'}); continue
 model=make_pipeline(SimpleImputer(strategy='median',add_indicator=True),RandomForestRegressor(n_estimators=120,min_samples_leaf=4,max_features=.8,random_state=42,n_jobs=2)); model.fit(tr[features_cols],tr.yield_t_ha); pr=model.predict(te[features_cols]); base=np.repeat(tr.yield_t_ha.median(),len(te))
 future.append({'crop':crop,'status':'EXPLORATORY_TEMPORAL_HOLDOUT','train_years':f'{min(tr.year)}-{max(tr.year)}','test_year':int(testyear),'n_train':len(tr),'n_test':len(te),'MAE_t_ha':mean_absolute_error(te.yield_t_ha,pr),'RMSE_t_ha':np.sqrt(mean_squared_error(te.yield_t_ha,pr)),'R2':r2_score(te.yield_t_ha,pr),'baseline_RMSE_t_ha':np.sqrt(mean_squared_error(te.yield_t_ha,base)),'warning':'Climate predictors are 2015-2024 summaries; not temporally matched to all survey years.'})
pd.DataFrame(future).to_csv(out/'temporal_holdout_diagnostic.csv',index=False)
# data audit summary
with open(out/'data_audit.txt','w') as f:
 f.write('AgriZone real-world yield validation audit\n')
 f.write(f'GROW-Africa LSMS workbook rows: {len(df):,}\nNigeria rows: {len(ng):,}\nSelected target crops: {", ".join(crops)}\n')
 f.write('Yield field used: YieldUsingGPS_ton_ha_ (derived using GPS area; ton/ha).\n')
 f.write('Outlier policy: exclude values above crop-specific 99.5th percentile from primary model fit, but preserve them and flag them in nigeria_yield_observation_audit.csv. This is a screening choice, not proof the observations are erroneous.\n')
 f.write('Spatial join: assign GPS coordinate to LGA polygon; if point not inside any polygon, nearest polygon centroid. Because source spatial precision can be 5 km, LGA assignments are approximate.\n')
 f.write('Predictors: AgriZone LGA mean rainfall, dry months, hot/cool/wet-season max temperature, soil pH, organic carbon, slope. Environmental climate summaries are 2015-2024 and do not match all historical yield years.\n')
 f.write('Validation: GroupKFold by assigned state, not a fully independent dataset; states can have different observation density. Temporal holdout diagnostic uses latest available year per crop but shares non-time-matched climate predictors.\n')
 f.write('Not validated: tomato (no Nigerian records in this LSMS file), and any crop with insufficient states/records. No claim of 774-LGA yield accuracy.\n')
print('FEATURES',len(features),'NGA',len(ng),'selected',len(selected),'valid',len(valid))
print(pd.DataFrame(summary).to_string(index=False))
print(pd.DataFrame(future).to_string(index=False))
