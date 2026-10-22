"""Download GBIF presence records for the 8 crops in Nigeria WITH quality fields.   pip install requests
Writes data/gbif_nigeria_detailed.csv: crop, lat, lon, basis, year, unc (coordinate uncertainty, m), institution, dataset, issues.
Then:  python scripts/gbif_quality.py data/gbif_nigeria_detailed.csv
       python scripts/validate.py --gbif data/gbif_nigeria_detailed.csv --strict
Needs internet access to api.gbif.org. One row is kept per (crop, lat, lon)."""
import csv, os, time, requests
CROPS = {"cocoa": "Theobroma cacao", "wheat": "Triticum aestivum", "cassava": "Manihot esculenta", "rice": "Oryza sativa",
         "sorghum": "Sorghum bicolor", "oilpalm": "Elaeis guineensis", "maize": "Zea mays", "tomato": "Solanum lycopersicum"}
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'gbif_nigeria_detailed.csv'); seen = set(); rows = []
for crop, name in CROPS.items():
    key = requests.get("https://api.gbif.org/v1/species/match", params={"name": name}, timeout=60).json()["usageKey"]; off = 0
    while True:
        r = requests.get("https://api.gbif.org/v1/occurrence/search", timeout=60, params={
            "taxonKey": key, "country": "NG", "hasCoordinate": "true", "hasGeospatialIssue": "false", "occurrenceStatus": "PRESENT",
            "decimalLatitude": "4,14", "decimalLongitude": "2.5,15", "limit": 300, "offset": off}).json()
        for o in r["results"]:
            k = (crop, o["decimalLatitude"], o["decimalLongitude"])
            if k in seen: continue
            seen.add(k)
            rows.append([crop, o["decimalLatitude"], o["decimalLongitude"], o.get("basisOfRecord", ""), o.get("year") or "",
                         o.get("coordinateUncertaintyInMeters", ""), o.get("institutionCode", ""), o.get("datasetKey", ""), ";".join(o.get("issues", []))])
        off += 300
        if r["endOfRecords"] or off >= 99000: break
        time.sleep(.3)
    print(crop, 'unique records so far:', len(rows))
with open(OUT, "w", newline="") as f:
    w = csv.writer(f); w.writerow(["crop", "lat", "lon", "basis", "year", "unc", "institution", "dataset", "issues"]); w.writerows(rows)
print('wrote', os.path.normpath(OUT))
