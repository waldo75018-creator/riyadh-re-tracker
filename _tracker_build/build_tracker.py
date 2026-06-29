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
    agg={}
    for r in rows:
        try:
            ar=float(r['area']); am=float(r['amount']); pm=float(r['ppm']); d=r['district']
        except: continue
        if ar<=0 or am<=0: continue
        land_deals.append([d,int(ar),int(am),int(pm),r['date']])
        a=agg.setdefault(d,[0.0,0.0,0]); a[0]+=am; a[1]+=ar; a[2]+=1
    land_deals.sort(key=lambda x:x[4],reverse=True)
    land_agg={d:[int(round(v[0]/v[1])),v[2]] for d,v in agg.items() if v[1]>0}
    land_updated=_dt.datetime.fromtimestamp(os.path.getmtime(LANDCSV)).strftime('%Y-%m-%d %H:%M')
else:
    land_updated='—'
LAND={'deals':land_deals[:400],'agg':land_agg,'updated':land_updated,'n':len(land_deals)}
EN=json.load(open(os.path.join(HERE,'en_names.json'),encoding='utf-8')) if os.path.exists(os.path.join(HERE,'en_names.json')) else {}
HIST=json.load(open(os.path.join(HERE,'history.json'),encoding='utf-8')) if os.path.exists(os.path.join(HERE,'history.json')) else {}
GEO=json.load(open(os.path.join(HERE,'geo_riyadh.json'),encoding='utf-8')) if os.path.exists(os.path.join(HERE,'geo_riyadh.json')) else {}
GQ=('Q%s %s'%(clean_qs[-1][-1],clean_qs[-1][:4])) if clean_qs else ''
META={'year':year,'gq':GQ,'years':yrs}
# --- deal-level transactions (latest quarter) for the Actual Transactions table ---
TX=[]; TXMETA={}
if files:
    _lastf=files[-1]
    _lq=re.search(r'-Q(\d)',_lastf).group(1)
    _dd=loadcity(_lastf).copy()
    _dd['date']=_dd['date_g'].astype(str).str.replace('/','-',regex=False).str.slice(0,10)
    _UM={'سكني':'R','تجاري':'C','زراعي':'A'}
    _dd['u']=_dd['cls'].astype(str).str.strip().map(_UM).fillna('O')
    _dd['npropi']=pd.to_numeric(_dd['nprop'],errors='coerce').fillna(1).astype(int)
    _dd=_dd.sort_values('date',ascending=False)
    for _,_r in _dd.head(5000).iterrows():
        TX.append([_r['d'],_r['date'],_r['u'],int(_r['price']),int(_r['area']),int(round(_r['ppm'])),int(_r['npropi'])])
    TXMETA={'period':str(year)+' Q'+_lq,'n':int(len(_dd)),'shown':len(TX)}
PAY=json.dumps({'mojp':MOJP,'sump':SUMP,'repi':REPI,'coords':COORDS,'land':LAND,'en':EN,'geo':GEO,'meta':META,'txns':TX,'txmeta':TXMETA},ensure_ascii=False)
tpl=open(os.path.join(HERE,'template.html'),encoding='utf-8').read()
html=tpl.replace('__PAYLOAD__',PAY)
import os as _os
with open(OUT,'w',encoding='utf-8') as _f:
    _f.write(html); _f.flush(); _os.fsync(_f.fileno())
assert _os.path.getsize(OUT)==len(html.encode('utf-8')), 'WRITE TRUNCATED %d/%d'%(_os.path.getsize(OUT),len(html.encode('utf-8')))
print('Rebuilt %s geo=%d res=%d com=%d'%(year,len(GEO),len(MOJ['res']),len(MOJ['com'])))
