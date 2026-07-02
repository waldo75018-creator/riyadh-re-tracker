#!/usr/bin/env python3
# Live rates and commodities from Yahoo Finance (public), baked server-side. ASCII-only, never raises.
import json, urllib.request, datetime
def _yq(sym):
    url="https://query1.finance.yahoo.com/v8/finance/chart/%s?interval=1d&range=5d"%sym
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req,timeout=12) as r: d=json.load(r)
    m=d["chart"]["result"][0]["meta"]
    return m.get("regularMarketPrice"), (m.get("chartPreviousClose") or m.get("previousClose"))
def _tile(k,px,pc,kind):
    if px is None or pc is None: return None
    if kind=="gold": v="$"+format(int(round(px)),",")
    elif kind=="yld": v="%.2f%%"%px
    else: v="$%.2f"%px
    diff=px-pc
    dr=1 if diff>0 else (-1 if diff<0 else 0)
    if kind=="yld": sub="%dbp"%abs(round(diff*100))
    elif pc: sub="%.2f%%"%abs(diff/pc*100.0)
    else: sub=""
    return {"k":k,"v":v,"sub":sub,"dir":dr}
def get_rates():
    now=(datetime.datetime.utcnow()+datetime.timedelta(hours=3)).strftime("%Y-%m-%d %H:%M")
    out={"updated":now,"market":[],
         "policy":[{"k":"Fed funds","v":"3.50-3.75%"},{"k":"SAMA repo","v":"4.25%"},{"k":"SAIBOR 3M","v":"4.79%"}],
         "policyAsOf":"Jul 2026"}
    for k,s,kind in [("Brent","BZ=F","usd"),("WTI","CL=F","usd"),("Gold","GC=F","gold"),("Nat gas","NG=F","usd"),("US 10Y","%5ETNX","yld")]:
        try:
            px,pc=_yq(s); t=_tile(k,px,pc,kind)
            if t: out["market"].append(t)
        except Exception as e:
            print("rates: %s failed: %s"%(k,e))
    return out
if __name__=="__main__":
    print(json.dumps(get_rates(),indent=1))
