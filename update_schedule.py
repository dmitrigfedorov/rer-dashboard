import json, os, sys, unicodedata, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

API = 'https://prim.iledefrance-mobilites.fr/marketplace/stop-monitoring'
LINE = 'STIF:Line::C01727:'
BUS_LINE = 'STIF:Line::C01288:'
BUS_STOPS = {'quai': 'STIF:StopArea:SP:50401:', 'vincennes': 'STIF:StopArea:SP:473115:'}
BUS_REFRESH = timedelta(minutes=10)
STATIONS = [('Ivry-sur-Seine','STIF:StopArea:SP:46366:'),('Bibliothèque François-Mitterrand','STIF:StopArea:SP:45301:')]
PARIS = ZoneInfo('Europe/Paris')

def many(v): return v if isinstance(v,list) else ([] if v is None else [v])
def repair_text(s):
    # Some API responses contain UTF-8 text decoded as Latin-1 upstream.
    if any(marker in s for marker in ('Ã', 'Â')):
        try: return s.encode('latin-1').decode('utf-8')
        except (UnicodeEncodeError, UnicodeDecodeError): pass
    return s
def val(v):
    if isinstance(v,dict): return val(v.get('value'))
    if isinstance(v,list): return ', '.join(filter(None,(val(x) for x in v)))
    return '' if v is None else repair_text(str(v))
def dt(v):
    if not v: return None
    x=datetime.fromisoformat(str(v).replace('Z','+00:00'))
    if x.tzinfo is None: x=x.replace(tzinfo=timezone.utc)
    return x.astimezone(timezone.utc)
def fetch(token, stop, now, line=LINE):
    q=urllib.parse.urlencode({'MonitoringRef':stop,'LineRef':line})
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
        rows.append({'dep':dep,'arr':dt(c.get('ExpectedArrivalTime')) or dep,'train':val(j.get('JourneyNote')),'dest':val(j.get('DestinationName')),'direction':val(j.get('DirectionName')),'display':val(j.get('DestinationDisplay')),'platform':val(c.get('DeparturePlatformName')),'status':val(c.get('DepartureStatus'))})
    return sorted(rows,key=lambda x:x['dep'])
def normalize(s):
    value=unicodedata.normalize('NFKD',s or '')
    return ''.join(c for c in value if not unicodedata.combining(c)).lower()

def bus_departures(token, stop, headsign, now):
    target=normalize(headsign)
    rows=[]
    for visit in fetch(token,stop,now,BUS_LINE):
        labels=normalize(' '.join((visit.get('dest',''),visit.get('direction',''),visit.get('display',''))))
        if target not in labels: continue
        rows.append({'from':visit['dep'].astimezone(PARIS).strftime('%H:%M'),'to':'','train':'325','destinationName':headsign,'platform':'','status':visit['status']})
        if len(rows)==3: break
    return rows

def prior_schedule(path):
    try: return json.loads(path.read_text(encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError): return {}

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
    now=datetime.now(timezone.utc)
    schedule_path=Path(__file__).with_name('schedule.json')
    previous=prior_schedule(schedule_path)
    data=[fetch(token,s,now) for _,s in STATIONS]
    directions=[{'title':STATIONS[0][0],'destination':STATIONS[1][0],'rows':pair(data[0],data[1])},{'title':STATIONS[1][0],'destination':STATIONS[0][0],'rows':pair(data[1],data[0])}]

    old_cards={c.get('card'):c for c in previous.get('cards',[]) if c.get('mode')=='bus'}
    bus_updated=dt(previous.get('busFetchedAt'))
    if bus_updated is None or now-bus_updated>=BUS_REFRESH:
        try:
            bus_quai=bus_departures(token,BUS_STOPS['quai'],'Quai de la Gare',now)
            bus_vincennes=bus_departures(token,BUS_STOPS['vincennes'],'Château de Vincennes',now)
            bus_updated=now
            print('Refreshed BUS 325 data.')
        except Exception as e:
            print('BUS 325 refresh failed; retaining the last available bus data: '+str(e),file=sys.stderr)
            bus_quai=old_cards.get('bus-quai',{}).get('rows',[])
            bus_vincennes=old_cards.get('bus-vincennes',{}).get('rows',[])
            if bus_updated is None: bus_updated=now
    else:
        bus_quai=old_cards.get('bus-quai',{}).get('rows',[])
        bus_vincennes=old_cards.get('bus-vincennes',{}).get('rows',[])

    cards=[
        {'card':'rer-ivry','mode':'rer','line':'C','title':STATIONS[0][0],'destination':STATIONS[1][0],'rows':directions[0]['rows']},
        {'card':'bus-quai','mode':'bus','line':'325','title':'Jean-Jacques Rousseau','destination':'Emile Durkheim','rows':bus_quai},
        {'card':'rer-bfm','mode':'rer','line':'C','title':STATIONS[1][0],'destination':STATIONS[0][0],'rows':directions[1]['rows']},
        {'card':'bus-vincennes','mode':'bus','line':'325','title':'Bibliothèque François-Mitterrand','destination':'Jean-Jacques Rousseau','rows':bus_vincennes}
    ]
    stamp=now.astimezone(PARIS).strftime('%d.%m.%Y, %H:%M:%S')
    out={'fetchedAtParis':stamp,'directions':directions,'cards':cards,'busFetchedAt':bus_updated.isoformat().replace('+00:00','Z') if bus_updated else None,'busFetchedAtParis':bus_updated.astimezone(PARIS).strftime('%d.%m.%Y, %H:%M:%S') if bus_updated else None}
    schedule_path.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Updated schedule.json at '+stamp+' Paris time')
if __name__=='__main__':
    try: main()
    except Exception as e: print('Schedule update failed: '+str(e),file=sys.stderr); raise
