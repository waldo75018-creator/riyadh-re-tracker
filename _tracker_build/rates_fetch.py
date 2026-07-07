#!/usr/bin/env python3
# Live rates and commodities from Yahoo Finance (public), baked server-side. ASCII-only, never raises.
import json, urllib.request, datetime
def _yq(sym):
    url="https://query1.finance.yahoo.com/v8/finance/chart/%s?interval=1d&range=5d"%sym
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req,timeout=12) as r: d=json.load(r)
    m=d["chart"]["result"][0]["meta"]
    return m.get("regularMarketPrice"), (m.get("chartPreviousClose") or m.get("previousClose"))
RANGES=[("1D","1d","5m"),("7D","5d","30m"),("1M","1mo","1d"),("6M","6mo","1d"),("1Y","1y","1d"),("5Y","5y","1wk")]
def _hist(sym):
    # per-range compact series {label:{"t":[epoch..],"c":[close..]}}; never raises
    h={}
    for lab,rng,itv in RANGES:
        try:
            url="https://query1.finance.yahoo.com/v8/finance/chart/%s?range=%s&interval=%s"%(sym,rng,itv)
            req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
            with urllib.request.urlopen(req,timeout=12) as r: d=json.load(r)
            res=d["chart"]["result"][0]
            ts=res.get("timestamp") or []
            q=(res.get("indicators",{}).get("quote") or [{}])[0]
            cl=q.get("close") or []
            t2=[];c2=[]
            for t,c in zip(ts,cl):
                if c is None: continue
                t2.append(int(t)); c2.append(round(float(c),2))
            if len(c2)>=2: h[lab]={"t":t2,"c":c2}
        except Exception as e:
            print("rates hist: %s %s failed: %s"%(sym,lab,e))
    return h
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
    return {"k":k,"v":v,"sub":sub,"dir":dr,"kind":kind}
def get_rates():
    now=(datetime.datetime.utcnow()+datetime.timedelta(hours=3)).strftime("%Y-%m-%d %H:%M")
    out={"updated":now,"market":[],
         "policy":[{"k":"Fed funds","v":"3.50-3.75%"},{"k":"SAMA repo","v":"4.25%"},{"k":"SAIBOR 3M","v":"4.79%"}],
         "policyAsOf":"Jul 2026"}
    for k,s,kind in [("Brent","BZ=F","usd"),("WTI","CL=F","usd"),("Gold","GC=F","gold"),("Nat gas","NG=F","usd"),("US 10Y","%5ETNX","yld")]:
        try:
            px,pc=_yq(s); t=_tile(k,px,pc,kind)
            if t:
                out["market"].append(t)
                hh=_hist(s)
                if hh: out.setdefault("hist",{})[k]=hh
        except Exception as e:
            print("rates: %s failed: %s"%(k,e))
    return out
if __name__=="__main__":
    print(json.dumps(get_rates(),indent=1))
