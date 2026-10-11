import os,argparse,random,time
from pathlib import Path
import numpy as np,pandas as pd,requests,yfinance as yf
ETFS='SOXL SOXX SMH SPY QQQ IWM DIA XLK XLF XLE XLV XLI XLY XLP XLU XLB XLC XLRE XBI IBB TLT GLD SLV TQQQ SQQQ ARKK KRE HYG'.split()
def get(url,params):
 r=requests.get('https://api.tradier.com/v1'+url,params=params,headers={'Authorization':'Bearer '+os.environ['TRADIER_TOKEN'],'Accept':'application/json'},timeout=25);r.raise_for_status();return r.json()
def liquidity(s):
 try:
  q=get('/markets/quotes',{'symbols':s})['quotes']['quote'];spot=float(q.get('last') or 0)
  dates=get('/markets/options/expirations',{'symbol':s})['expirations']['date'];dates=[dates] if isinstance(dates,str) else dates
  today=pd.Timestamp.now().normalize();choices=[]
  for lo,hi,target in [(4,14,7),(25,50,35)]:
   ds=[d for d in dates if lo<=(pd.Timestamp(d)-today).days<=hi]
   if ds:choices.append(min(ds,key=lambda d:abs((pd.Timestamp(d)-today).days-target)))
  spreads=[];vol=[];oi=[]
  for date in choices:
   opts=get('/markets/options/chains',{'symbol':s,'expiration':date})['options']['option']
   if isinstance(opts,dict):opts=[opts]
   for side in ('call','put'):
    subset=sorted((x for x in opts if x.get('option_type')==side),key=lambda x:abs(float(x['strike'])-spot))[:3]
    for x in subset:
     b=float(x.get('bid') or 0);a=float(x.get('ask') or 0)
     if b>0 and a>=b and (a+b)/2>=.1:
      spreads.append((a-b)/((a+b)/2));vol.append(int(x.get('volume') or 0));oi.append(int(x.get('open_interest') or 0))
  if len(spreads)<6:return None
  return dict(symbol=s,spread=float(np.median(spreads)),volume=sum(vol),open_interest=sum(oi),contracts=len(spreads))
 except Exception as e:print('liquidity unavailable',s,str(e)[:90]);return None
def select(out,seed):
 if not os.getenv('TRADIER_TOKEN'):raise SystemExit('Set TRADIER_TOKEN (live quote entitlement) or provide --stocks-file')
 cache=out/'top200.csv'
 if cache.exists():top=pd.read_csv(cache)
 else:
  t=pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')[0];rows=[]
  for i,r in t.iterrows():
   s=r['Symbol'].replace('.','-')
   try:cap=yf.Ticker(s).fast_info.get('market_cap')
   except Exception:cap=None
   if cap:rows.append((s,int(cap),r['GICS Sector']))
   if i%50==0:print('market cap scan',i,flush=True)
  top=pd.DataFrame(rows,columns=['symbol','market_cap','sector']).nlargest(200,'market_cap');top.to_csv(cache,index=False)
 snap=out/'liquidity.csv';data=pd.read_csv(snap).to_dict('records') if snap.exists() else [];done={x['symbol'] for x in data}
 for s in top.symbol:
  if s in done:continue
  x=liquidity(s)
  if x:data.append(x);pd.DataFrame(data).to_csv(snap,index=False)
  time.sleep(.15)
 d=pd.DataFrame(data);d=d[(d.spread<=.20)&(d.volume>=100)&(d.open_interest>=500)].copy()
 d['score']=np.log1p(d.volume)+.3*np.log1p(d.open_interest)-12*d.spread
 d=d.sort_values('score',ascending=False);d.to_csv(out/'eligible_ranked.csv',index=False)
 pool=d.head(80).symbol.tolist()
 if len(pool)<20:raise SystemExit('Fewer than 20 eligible stocks; no fallback to unverified liquidity.')
 selected=random.Random(seed).sample(pool,20);pd.DataFrame({'symbol':selected,'seed':seed}).to_csv(out/'selected_20.csv',index=False)
 return selected,dict(zip(top.symbol,top.sector))
def ratio(a,b):return a/b.replace(0,np.nan)
def build(s,sector,start,end,maxx):
 d=yf.download(s,start=start,end=end,auto_adjust=True,progress=False,threads=False)
 if isinstance(d.columns,pd.MultiIndex):d.columns=d.columns.get_level_values(0)
 d=d[['Open','High','Low','Close','Volume']].dropna();d=d[d.Volume>0]
 if len(d)<250:raise ValueError('Not enough bars')
 o,h,l,c,v=[d[x].astype(float) for x in ['Open','High','Low','Close','Volume']];prev=c.shift(1)
 tr=pd.concat([h-l,(h-prev).abs(),(l-prev).abs()],axis=1).max(axis=1)
 atr=tr.ewm(alpha=1/21,adjust=False).mean();a=pd.DataFrame(index=d.index)
 a['symbol']=s;a['sector']=sector;a['anchor_dt']=d.index.strftime('%Y-%m-%d');a['anchor_close']=c;a['atr21']=atr
 a['atr5_atr21']=ratio(tr.ewm(alpha=1/5,adjust=False).mean(),atr)
 a['atr21_atr63']=ratio(atr,tr.ewm(alpha=1/63,adjust=False).mean())
 lr=np.log(c/prev)
 for k in (5,21,63):a[f'rv{k}']=lr.rolling(k).std()*np.sqrt(252)
 a['rv5_rv21']=ratio(a.rv5,a.rv21);a['rv21_rv63']=ratio(a.rv21,a.rv63)
 for k in (5,10,20,40,60):
  change=c-c.shift(k);path=c.diff().abs().rolling(k).sum()
  a[f'slope_{k}']=ratio(change,k*atr);a[f'eff_{k}']=ratio(change.abs(),path);a[f'signed_eff_{k}']=ratio(change,path)
 for k in (10,20,60,126):
  hi=h.rolling(k).max();lo=l.rolling(k).min()
  a[f'range_pos_{k}']=ratio(c-lo,hi-lo);a[f'range_width_atr_{k}']=ratio(hi-lo,atr)
 body=c-o;ran=h-l
 a['body_atr']=ratio(body,atr);a['body_fraction']=ratio(body.abs(),ran)
 a['upper_wick_fraction']=ratio(h-pd.concat([o,c],axis=1).max(axis=1),ran)
 a['lower_wick_fraction']=ratio(pd.concat([o,c],axis=1).min(axis=1)-l,ran)
 a['anchor_tr_atr']=ratio(tr,atr);gap=o-prev;a['gap_atr']=ratio(gap,atr);a['abs_gap_atr']=ratio(gap.abs(),atr)
 a['gap5_mean_abs_atr']=ratio(gap.abs().rolling(5).mean(),atr);a['gap20_max_abs_atr']=ratio(gap.abs().rolling(20).max(),atr)
 a['volume_rel20']=ratio(v,v.rolling(20).mean());a['volume_med20_med63']=ratio(v.rolling(20).median(),v.rolling(63).median())
 dv=v*c;a['dollar_volume_rel20']=ratio(dv,dv.rolling(20).mean())
 for k in (60,126):
  past=pd.concat([c.shift(j) for j in range(1,k+1)],axis=1)
  a[f'price_zone_hit_rate_{k}']=past.sub(c,axis=0).abs().le(atr*.5,axis=0).sum(axis=1)/k
 a=a.replace([np.inf,-np.inf],np.nan).dropna();rows=[];indices=d.index.get_indexer(a.index)
 hv=h.to_numpy();lv=l.to_numpy();cv=c.to_numpy()
 for x in range(1,maxx+1):
  valid=indices[indices+x<len(d)];n=len(valid)
  if not n:continue
  aa=a.iloc[:n];base=aa.anchor_close.to_numpy();av=aa.atr21.to_numpy()
  ending=cv[valid+x];up=np.array([hv[i+1:i+x+1].max() for i in valid]);down=np.array([lv[i+1:i+x+1].min() for i in valid]);r=(ending-base)/av
  rows.append(pd.DataFrame(dict(symbol=s,anchor_dt=aa.anchor_dt,x_days=x,end_close=ending,terminal_return_atr=r,terminal_return_pct=(ending/base-1)*100,up_terminal_atr=np.maximum(r,0),down_terminal_atr=np.maximum(-r,0),up_excursion_atr=np.maximum((up-base)/av,0),down_excursion_atr=np.maximum((base-down)/av,0),up_excursion_pct=np.maximum((up/base-1)*100,0),down_excursion_pct=np.maximum((1-down/base)*100,0))))
 return a.reset_index(drop=True),pd.concat(rows,ignore_index=True)
def main():
 p=argparse.ArgumentParser();p.add_argument('--out',default='range_output');p.add_argument('--start',default='2015-01-01');p.add_argument('--end');p.add_argument('--max-x',type=int,default=60);p.add_argument('--seed',type=int,default=20261010);p.add_argument('--stocks-file');p.add_argument('--skip-stocks',action='store_true');p.add_argument('--only');args=p.parse_args()
 out=Path(args.out);out.mkdir(parents=True,exist_ok=True);symbols=ETFS.copy();sectors={s:'ETF' for s in ETFS}
 if args.stocks_file:
  t=pd.read_csv(args.stocks_file);symbols+=t.symbol.tolist()
  if 'sector' in t:sectors.update(dict(zip(t.symbol,t.sector)))
 elif not args.skip_stocks:
#   stocks,sector_map=select(out,args.seed);symbols+=stocks;sectors.update(sector_map)
# Only perform S&P/options-liquidity stock selection when we are
# running the normal expanded-universe collection.
# --only is intended to bypass ALL universe discovery.
  if not args.only:
    stocks, sector_map = select(out, args.seed)
    symbols += stocks
    sectors.update(sector_map)
 if args.only:symbols=[x.strip() for x in args.only.split(',')]
 manifest=[]
 for s in dict.fromkeys(symbols):
  try:
   print('Collecting',s,flush=True);a,b=build(s,sectors.get(s,'Unknown'),args.start,args.end,args.max_x)
   a.to_csv(out/f'{s}_anchors.csv.gz',index=False);b.to_csv(out/f'{s}_outcomes.csv.gz',index=False)
   manifest.append(dict(symbol=s,anchors=len(a),outcomes=len(b),start=a.anchor_dt.min(),end=a.anchor_dt.max(),status='ok'))
  except Exception as e:manifest.append(dict(symbol=s,status='error',error=str(e)));print('ERROR',s,e)
  pd.DataFrame(manifest).to_csv(out/'manifest.csv',index=False)
 print('Finished. Keep outputs per symbol to support resumable merges and audits.')
if __name__=='__main__':main()
