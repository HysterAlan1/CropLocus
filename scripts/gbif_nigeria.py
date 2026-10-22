# Download GBIF presence records for the 8 crops in Nigeria. pip install requests
import requests, csv, time
CROPS = {"cocoa":"Theobroma cacao","wheat":"Triticum aestivum","cassava":"Manihot esculenta","rice":"Oryza sativa","sorghum":"Sorghum bicolor","oilpalm":"Elaeis guineensis","maize":"Zea mays","tomato":"Solanum lycopersicum"}
rows=[]
for crop,name in CROPS.items():
    key=requests.get("https://api.gbif.org/v1/species/match",params={"name":name}).json()["usageKey"]
    off=0
    while True:
        r=requests.get("https://api.gbif.org/v1/occurrence/search",params={"taxonKey":key,"country":"NG","hasCoordinate":"true","hasGeospatialIssue":"false","decimalLatitude":"4,14","decimalLongitude":"2.5,15","limit":300,"offset":off}).json()
        for o in r["results"]:rows.append([crop,o["decimalLatitude"],o["decimalLongitude"],o.get("basisOfRecord",""),o.get("year") or (o.get("eventDate") or "")[:4]])
        off+=300
        if r["endOfRecords"] or off>=9900:break
        time.sleep(.3)
# GBIF returns many identical (crop, lat, lon) rows; keep one per location
seen=set();uniq=[]
for r_ in rows:
    k_=(r_[0],r_[1],r_[2])
    if k_ not in seen:seen.add(k_);uniq.append(r_)
print(len(rows),"rows ->",len(uniq),"after dropping duplicate locations")
rows=uniq
with open("gbif_nigeria.csv","w",newline="") as f:
    w=csv.writer(f);w.writerow(["crop","lat","lon","basis","year"]);w.writerows(rows)
