#!/usr/bin/env python3
# Collect Riyadh RAW-LAND deals from Suhail (api2.suhail.ai) -> raw_land_deals.csv (drop-in for build_tracker.py).
# Suhail exposes full trailing-~12-month deal history per neighbourhood (vs SREM's ~5-recent cap).
import json, os, csv, time, urllib.request, concurrent.futures as cf
HERE = os.path.dirname(os.path.abspath(__file__))
NB   = os.path.join(HERE, "suhail_neighbourhoods.json")
OUT  = os.path.join(HERE, "raw_land_deals.csv")
H = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
     "Origin":"https://www.suhail.ai","Referer":"https://www.suhail.ai/","Accept":"application/json, text/plain, */*",
     "Cache-Control":"no-cache","Pragma":"no-cache"}
LANDWORDS = ["أرض", "ارض"]  # 'أرض' / 'ارض'
def _get(nid, page=1, size=500):
    url = "https://api2.suhail.ai/transactions/neighbourhood?regionId=10&neighbourhoodId=%s&page=%d&pageSize=%d&_ts=%d" % (nid, page, size, int(time.time()*1000))
    req = urllib.request.Request(url, headers=H)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)
def _is_land(t):
    for k in ("type","propertyType","landUseaDetailed","metricsType","landUsageGroup"):
        v = t.get(k) or ""
        if any(w in v for w in LANDWORDS):
            # exclude 'أرض زراعية' (agricultural) only if you want; keep all land for now
            return True
    return False
def _fetch(nb):
    nid = nb["id"]; name = nb.get("name","")
    rows = []
    try:
        j = _get(nid, 1, 500)
    except Exception as e:
        return rows
    rows = list(j.get("data") or [])
    try:
        pc = int(j["meta"]["pagination"]["pageCount"])
    except Exception:
        pc = 1
    for p in range(2, min(pc, 8) + 1):   # cap pages/district to avoid runaways
        try:
            rows += list(_get(nid, p, 500).get("data") or [])
        except Exception:
            break
    out = []
    for t in rows:
        if not _is_land(t):
            continue
        try:
            ar = float(t.get("area") or t.get("totalArea") or 0)
            am = float(t.get("transactionPrice") or 0)
            pm = float(t.get("priceOfMeter") or 0)
        except Exception:
            continue
        if ar <= 0 or am <= 0:
            continue
        if pm <= 0:
            pm = am / ar
        tid = str(t.get("transactionNumber") or t.get("orignalTransactionNum") or "")
        if not tid:
            continue
        out.append({"id": tid,
                    "district": (t.get("neighborhood") or name or "?").strip(),
                    "area": int(ar), "amount": int(am), "ppm": int(round(pm)),
                    "date": (t.get("transactionDate") or "")[:10]})
    return out
def main():
    nbs = [n for n in json.load(open(NB, encoding="utf-8")) if n.get("province_id") == 101000]
    deals = {}
    ok = 0
    with cf.ThreadPoolExecutor(max_workers=12) as ex:
        for res in ex.map(_fetch, nbs):
            if res: ok += 1
            for d in res:
                deals[d["id"]] = d
    rows = sorted(deals.values(), key=lambda r: r["date"], reverse=True)
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id","district","area","amount","ppm","date"])
        w.writeheader(); w.writerows(rows)
    print("suhail land deals stored:%d  neighbourhoods_with_data:%d/%d" % (len(rows), ok, len(nbs)))
if __name__ == "__main__":
    main()
