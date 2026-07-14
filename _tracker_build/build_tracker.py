#!/usr/bin/env python3
# Rebuilds riyadh-real-estate-tracker.html from the latest civillizard/Saudi-Real-Estate-Data quarters.
import subprocess,sys
try:
    import pandas
except ImportError:
    subprocess.run([sys.executable,"-m","pip","install","pandas","--break-system-packages","-q"],check=True)
import pandas as pd, glob, json, re, os, tempfile
HERE=os.path.dirname(os.path.abspath(__file__)); OUT=os.path.join(HERE,'..','riyadh-real-estate-tracker.html')
REPO=os.path.join(tempfile.gettempdir(),'srd')
if not os.path.isdir(REPO):
    subprocess.run(['git','clone','--depth','1','https://github.com/civillizard/Saudi-Real-Estate-Data.git',REPO],check=True)
else:
    subprocess.run(['git','-C',REPO,'pull','--depth','1'],check=False)
os.chdir(REPO)
cols=['region','city','district','ref','date_g','date_h','cls','nprop','price','area']
def load(f): return pd.read_csv(f,header=0,names=cols,compression='gzip' if f.endswith('.gz') else None)
def clean(d):
    for c in ['price','area']:
        d[c]=pd.to_numeric(d[c].astype(str).str.replace(',','').str.replace('"',''),errors='coerce')
    d=d.dropna(subset=['price','area']); d=d[(d['area']>20)&(d['price']>10000)]
    d['ppm']=d['price']/d['area']; d=d[(d['ppm']>=200)&(d['ppm']<=150000)]
    d['d']=d['district'].astype(str).str.replace('الرياض/','',regex=False).str.replace('الرياض /','',regex=False).str.replace('حي','',regex=False).str.strip()
    return d
# build MOJ district aggregates for EACH period: last 5 years, full-year + each quarter
allyrs=sorted(set(re.search(r'(20\d\d)-Q',f).group(1) for f in glob.glob('moj/sales/MOJ-Sales-*-Q*.csv*')))
yrs=allyrs[-5:]; year=yrs[-1]
BANDS=[('S',0,300),('M',300,600),('L',600,1000),('XL',1000,9e9)]
def wppm(s): return int(round(s['price'].sum()/s['area'].sum())) if len(s) else 0
def build(df,cl):
    out=[]
    for dn,g in df[df['cls']==cl].groupby('d'):
        if len(g)<3: continue
        rec={'d':dn,'all':[wppm(g),int(len(g))],'b':{}}
        for bn,lo,hi in BANDS:
            gb=g[(g['area']>=lo)&(g['area']<hi)]
            if len(gb)>=3: rec['b'][bn]=[wppm(gb),int(len(gb))]
        out.append(rec)
    out.sort(key=lambda r:-r['all'][0]); return out
def loadcity(f):
    raw=load(f); return clean(raw[raw['city']=='الرياض'].copy())
MOJP={}; SUMP={}
def addperiod(key,d):
    MOJP[key]={'res':build(d,'سكني'),'com':build(d,'تجاري')}
    SUMP[key]={'res':[wppm(d[d['cls']=='سكني']),int(len(d[d['cls']=='سكني']))],'com':[wppm(d[d['cls']=='تجاري']),int(len(d[d['cls']=='تجاري']))]}
for y in yrs:
    qframes={}
    for f in sorted(glob.glob(f'moj/sales/MOJ-Sales-{y}-Q*.csv*')):
        qframes['Q'+re.search(r'-Q(\d)',f).group(1)]=loadcity(f)
    if not qframes: continue
    addperiod(y, pd.concat(list(qframes.values())))
    for qn in sorted(qframes): addperiod(y+qn, qframes[qn])
files=sorted(glob.glob(f'moj/sales/MOJ-Sales-{year}-Q*.csv*'))
MOJ=MOJP[year]; MOJ_sum=SUMP[year]
TM={'قطعة أرض سكني':'resLand','فيلا سكني':'villa','شقة سكني':'apt','قطعة أرض تجاري':'comLand','أرض زراعية':'agriLand','الرقم القياسي العام':'general'}
king={}; riy={}
for f in sorted(glob.glob('gastat/REPI-20*-Q*.csv')):
    q=re.search(r'(20\d\d)-Q(\d)',f); qq=f"{q.group(1)}Q{q.group(2)}"; d=pd.read_csv(f)
    if 'البند' not in d.columns: continue
    for _,r in d.iterrows():
        reg=str(r['المنطقة الإدارية']); it=str(r['البند']).strip(); v=r['الرقم القياسي']
        if reg=='المملكة' and it in TM: king.setdefault(qq,{})[TM[it]]=round(float(v),1)
        if reg=='الرياض' and it=='الرقم القياسي العام': riy[qq]=round(float(v),1)
qs=[q for q in sorted(king) ]
# drop quarters whose riyadh general looks like an outlier (>15 below neighbours)
clean_qs=[q for q in qs if riy.get(q) and riy.get(q)>95]
REPI={'quarters':clean_qs,'king':{k:[king[q].get(k) for q in clean_qs] for k in ['resLand','villa','apt','comLand','agriLand','general']},'riyadhGeneral':[riy.get(q) for q in clean_qs]}
COORDS=json.load(open(os.path.join(HERE,'coords.json'),encoding='utf-8'))
# --- raw land deals from SREM collector ---
import csv as _csv, datetime as _dt
LANDCSV=os.path.join(HERE,'raw_land_deals.csv'); land_deals=[]; land_agg={}
if os.path.exists(LANDCSV):
    rows=list(_csv.DictReader(open(LANDCSV,encoding='utf-8')))
    # top-up with near-real-time SREM deals (Suhail lags/stalls); dedup on (date,area,amount)
    SREMCSV=os.path.join(HERE,'srem_recent.csv')
    if os.path.exists(SREMCSV):
        def _k(r):
            try: return (r['date'],int(float(r['area'])),int(float(r['amount'])))
            except: return None
        _seen={_k(r) for r in rows}
        _add=[r for r in _csv.DictReader(open(SREMCSV,encoding='utf-8')) if _k(r) and _k(r) not in _seen]
        rows+= _add
        print('land merge: +%d SREM-only deals over %d suhail'%(len(_add),len(rows)-len(_add)))
    agg={}
    for r in rows:
        try:
            ar=float(r['area']); am=float(r['amount']); pm=float(r['ppm']); d=r['district']
        except: continue
        if ar<=0 or am<=0: continue
        land_deals.append([d,int(ar),int(am),int(pm),r['date']])
        agg.setdefault(d,[]).append(pm if pm>0 else am/ar)
    land_deals.sort(key=lambda x:x[4],reverse=True)
    # median SAR/m2 per district (robust to mega-parcel outliers that wreck a value-weighted avg)
    land_agg={d:[int(round(sorted(v)[len(v)//2])),len(v)] for d,v in agg.items() if v}
    land_updated=_dt.datetime.fromtimestamp(os.path.getmtime(LANDCSV)).strftime('%Y-%m-%d %H:%M')
else:
    land_updated='—'
# ship ALL deals compactly: district as index into 'dists', date as yyyymmdd int (template decodes)
_dlist=sorted({d[0] for d in land_deals})
_didx={d:i for i,d in enumerate(_dlist)}
_comp=[[_didx[d[0]],d[1],d[2],d[3],int(d[4].replace('-','') or 0)] for d in land_deals]
LAND={'deals':_comp,'dists':_dlist,'agg':land_agg,'updated':land_updated,'n':len(land_deals)}
EN=json.load(open(os.path.join(HERE,'en_names.json'),encoding='utf-8')) if os.path.exists(os.path.join(HERE,'en_names.json')) else {}
HIST=json.load(open(os.path.join(HERE,'history.json'),encoding='utf-8')) if os.path.exists(os.path.join(HERE,'history.json')) else {}
GEO=json.load(open(os.path.join(HERE,'geo_riyadh.json'),encoding='utf-8')) if os.path.exists(os.path.join(HERE,'geo_riyadh.json')) else {}
GQ=('Q%s %s'%(clean_qs[-1][-1],clean_qs[-1][:4])) if clean_qs else ''
META={'year':year,'gq':GQ,'years':yrs}
# --- deal-level transactions (latest quarter) for the Actual Transactions table ---
TX=[]; TXMETA={}; TXD=[]
if files:
    _parts=[]
    for _f in files:
        _p=loadcity(_f).copy(); _parts.append(_p)
    _dd=pd.concat(_parts)
    _dd['date']=_dd['date_g'].astype(str).str.replace('/','-',regex=False).str.slice(0,10)
    _UM={'سكني':0,'تجاري':1,'زراعي':2}
    _dd['u']=_dd['cls'].astype(str).str.strip().map(_UM).fillna(3).astype(int)
    _dd['npropi']=pd.to_numeric(_dd['nprop'],errors='coerce').fillna(1).astype(int)
    _dd=_dd.sort_values('date',ascending=False).head(60000)
    # compact: district index + yyyymmdd int + use index (R/C/A/O); template decodes
    TXD=sorted(_dd['d'].unique()); _txdi={d:i for i,d in enumerate(TXD)}
    for _,_r in _dd.iterrows():
        _ds=str(_r['date']).replace('-','')[:8]
        TX.append([_txdi[_r['d']],int(_ds) if _ds.isdigit() else 0,int(_r['u']),int(_r['price']),int(_r['area']),int(round(_r['ppm'])),int(_r['npropi'])])
    _qn=sorted(re.search(r'-Q(\d)',_f).group(1) for _f in files)
    TXMETA={'period':str(year)+' (Q'+_qn[0]+'-Q'+_qn[-1]+')','n':int(len(_dd)),'shown':len(TX)}
# --- rates and commodities (helper module; never fatal) ---
try:
    import rates_fetch; RATES=rates_fetch.get_rates()
except Exception as _e:
    print("rates failed:",_e); RATES={}
PAY=json.dumps({'mojp':MOJP,'sump':SUMP,'repi':REPI,'coords':COORDS,'land':LAND,'en':EN,'geo':GEO,'meta':META,'txns':TX,'txd':TXD,'txmeta':TXMETA,'rates':RATES},ensure_ascii=False)
tpl=open(os.path.join(HERE,'template.html'),encoding='utf-8').read()
html=tpl.replace('__PAYLOAD__',PAY)
import os as _os
with open(OUT,'w',encoding='utf-8') as _f:
    _f.write(html); _f.flush(); _os.fsync(_f.fileno())
assert _os.path.getsize(OUT)==len(html.encode('utf-8')), 'WRITE TRUNCATED %d/%d'%(_os.path.getsize(OUT),len(html.encode('utf-8')))
print('build OK:',OUT,os.path.getsize(OUT),'bytes')
