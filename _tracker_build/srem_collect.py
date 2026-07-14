#!/usr/bin/env python3
# Near-real-time top-up: SREM public GetAreaInfo publishes deals within days, while Suhail can lag/stall
# for weeks. City-level first (freshest), then rotating district sweep. Accumulates into srem_recent.csv
# (dedup by Id, pruned to ~180 days); build_tracker.py merges it over the Suhail snapshot.
import json,os,csv,time,urllib.request,concurrent.futures as cf
HERE=os.path.dirname(os.path.abspath(__file__))
API="https://prod-srem-api-srem.moj.gov.sa/api/v1/Dashboard/GetAreaInfo"
CODES=os.path.join(HERE,"land_district_codes.json"); OUTCSV=os.path.join(HERE,"srem_recent.csv")
OFFF=os.path.join(HERE,"srem_offset.txt")
def call(body):
    try:
        req=urllib.request.Request(API,data=json.dumps(body).encode(),headers={"Content-Type":"application/json","User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36","Accept":"application/json, text/plain, */*","Origin":"https://srem.moj.gov.sa","Referer":"https://srem.moj.gov.sa/"})
        with urllib.request.urlopen(req,timeout=9) as r: return json.loads(r.read().decode())
    except Exception: return None
LAND_WORDS=["أرض","ارض"]
def is_land(u):
    u=(u or "").strip()
    return u=="" or any(w in u for w in LAND_WORDS)
def mk(t,n):
    ar=int(float(t.get("TransArea") or 0)); am=int(float(t.get("TransAmount") or 0))
    pm=int(round(t.get("PricePerMeterSquare") or 0)) or (int(round(am/ar)) if ar>0 else 0)
    return {"id":"s"+str(t.get("Id")),"district":n,"area":ar,"amount":am,"ppm":pm,"date":(t.get("TransDate") or "")[:10]}
deals=[]
# 1) CITY-LEVEL first — fresher feed, carries NHName (district)
cj=call({"periodCategory":"Y","period":1,"areaSerial":1,"areaType":"C","cityCode":1})
if cj and cj.get("Data"):
    for t in (cj["Data"].get("Transactions") or []):
        if is_land(t.get("UnitType")):
            deals.append(mk(t,(t.get("NHName") or "").strip() or "?"))
city_run=len(deals)
# 2) ROTATING DISTRICT SWEEP
codes=list(json.load(open(CODES,encoding="utf-8")).items())
off=0
if os.path.exists(OFFF):
    try: off=int(open(OFFF).read().strip())
    except: off=0
off=off%len(codes); codes=codes[off:]+codes[:off]
DEADLINE=time.time()+60
def poll(it):
    n,c=it; j=call({"periodCategory":"Y","period":1,"areaSerial":c,"areaType":"D","cityCode":1}); out=[]
    if j and j.get("Data"):
        for t in (j["Data"].get("Transactions") or []):
            if is_land(t.get("UnitType")): out.append(mk(t,n))
    return out
done=0
ex=cf.ThreadPoolExecutor(max_workers=8)
futmap={ex.submit(poll,it):it for it in codes}
for f in cf.as_completed(futmap):
    if time.time()>DEADLINE: break
    try: deals+=f.result(timeout=max(0.1,DEADLINE-time.time()))
    except Exception: pass
    done+=1
ex.shutdown(wait=False,cancel_futures=True)
open(OFFF,"w").write(str((off+done)%len(codes)))
# merge + dedup
existing={}
if os.path.exists(OUTCSV):
    for row in csv.DictReader(open(OUTCSV,encoding="utf-8")): existing[row["id"]]=row
for d in deals: existing[d["id"]]={k:str(v) for k,v in d.items()}
import datetime as _dt
_cut=(_dt.date.today()-_dt.timedelta(days=180)).isoformat()
rows=sorted((r for r in existing.values() if (r.get("date") or "")>=_cut),key=lambda r:r["date"],reverse=True)
with open(OUTCSV,"w",encoding="utf-8",newline="") as f:
    w=csv.DictWriter(f,fieldnames=["id","district","area","amount","ppm","date"]); w.writeheader(); w.writerows(rows)
print("city_run:%d district_done:%d/%d run_total:%d stored:%d"%(city_run,done,len(codes),len(deals),len(rows)))
