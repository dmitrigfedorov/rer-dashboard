import json, os, sys, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

API = 'https://prim.iledefrance-mobilites.fr/marketplace/stop-monitoring'
LINE = 'STIF:Line::C01727:'
STATIONS = [('Ivry-sur-Seine','STIF:StopArea:SP:46366:'),('Bibliothèque François-Mitterrand','STIF:StopArea:SP:45301:')]
PARIS = ZoneInfo('Europe/Paris')

def many(v): return v if isinstance(v,list) else ([] if v is None else [v])
def val(v):
    if isinstance(v,dict): return val(v.get('value'))
    if isinstance(v,list): return ', '.join(filter(None,(val(x) for x in v)))
    return '' if v is None else str(v)
def dt(v):
    if not v: return None
    x=datetime.fromisoformat(str(v).replace('Z','+00:00'))
    if x.tzinfo is None: x=x.replace(tzinfo=timezone.utc)
    return x.astimezone(timezone.utc)
def fetch(token, stop, now):
    q=urllib.parse.urlencode({'MonitoringRef':stop,'LineRef':LINE})
    req=urllib.request.Request(API+'?'+q,headers={'apikey':token,'Accept':'application/json','User-Agent':'rer-dashboard/1.0'})
    with urllib.request.urlopen(req,timeout=25) as r: data=json.load(r)
    delivery=data.get('Siri',{}).get('ServiceDelivery',{}).get('StopMonitoringDelivery',[])
    visits=[]
    for d in many(delivery): visits += many(d.get('MonitoredStopVisit'))
    rows=[]
    for v in visits:
        j=v.get('MonitoredVehicleJourney') or {}; c=j.get('MonitoredCall') or {}
        dep=dt(c.get('ExpectedDepartureTime') or c.get('AimedDepartureTime'))
        if not dep or dep < now-timedelta(minutes=1): continue
        rows.append({'dep':dep,'arr':dt(c.get('ExpectedArrivalTime')) or dep,'train':val(j.get('JourneyNote')),'dest':val(j.get('DestinationName')),'platform':val(c.get('DeparturePlatformName')),'status':val(c.get('DepartureStatus'))})
    return sorted(rows,key=lambda x:x['dep'])
def pair(a,b):
    result=[]; seen=set()
    for x in a:
        matches=[y for y in b if y['train']==x['train'] and y['dest']==x['dest'] and x['dep']<y['dep']<=x['dep']+timedelta(minutes=7)]
        if not matches: continue
        y=matches[0]; row={'from':x['dep'].astimezone(PARIS).strftime('%H:%M'),'to':y['arr'].astimezone(PARIS).strftime('%H:%M'),'train':x['train'],'destinationName':x['dest'],'platform':x['platform'],'status':x['status']}
        key=tuple(row[k] for k in ('from','to','train','destinationName'))
        if key not in seen: result.append(row); seen.add(key)
        if len(result)==3: break
    return result
def main():
    token=os.environ.get('IDFM_API_TOKEN')
    if not token: raise RuntimeError('Missing Actions secret IDFM_API_TOKEN')
    now=datetime.now(timezone.utc); data=[fetch(token,s,now) for _,s in STATIONS]
    out={'fetchedAtParis':now.astimezone(PARIS).strftime('%d.%m.%Y, %H:%M:%S'),'directions':[{'title':STATIONS[0][0],'destination':STATIONS[1][0],'rows':pair(data[0],data[1])},{'title':STATIONS[1][0],'destination':STATIONS[0][0],'rows':pair(data[1],data[0])}]}
    Path(__file__).with_name('schedule.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Updated schedule.json at '+out['fetchedAtParis']+' Paris time')
if __name__=='__main__':
    try: main()
    except Exception as e: print('Schedule update failed: '+str(e),file=sys.stderr); raise
