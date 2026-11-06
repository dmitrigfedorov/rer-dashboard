import json, os, sys, unicodedata, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

API = 'https://prim.iledefrance-mobilites.fr/marketplace/stop-monitoring'
LINE = 'STIF:Line::C01727:'
BUS_LINE = 'STIF:Line::C01288:'
BUS125_LINE = 'STIF:Line::C01154:'
BUS323_LINE = 'STIF:Line::C01287:'
BUS_STOPS = {'quai': 'STIF:StopArea:SP:50401:', 'vincennes': 'STIF:StopArea:SP:473115:', 'moliere': 'STIF:StopArea:SP:46365:'}
BUS_REFRESH = timedelta(minutes=5)
STATIONS = [('Ivry-sur-Seine','STIF:StopArea:SP:46366:'),('Bibliothèque François-Mitterrand','STIF:StopArea:SP:45301:')]
# Ordered from the western RER C branch toward Ivry, so BFM opens with its three preceding stations visible.
RER_STATIONS = [
    ('champ-de-mars','Champ de Mars - Tour Eiffel','STIF:StopArea:SP:58757:'),
    ('pont-de-lalma',"Pont de l'Alma",'STIF:StopArea:SP:415091:'),
    ('invalides','Invalides','STIF:StopArea:SP:470540:'),
    ('musee-dorsay',"Musée d'Orsay",'STIF:StopArea:SP:45705:'),
    ('saint-michel','Saint-Michel Notre-Dame','STIF:StopArea:SP:44877:'),
    ('austerlitz',"Gare d'Austerlitz",'STIF:StopArea:SP:43072:'),
    ('bfm',STATIONS[1][0],STATIONS[1][1]),
]
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
    q=urllib.parse.urlencode({'MonitoringRef':stop,'LineRef':line,'MaximumStopVisits':3})
    req=urllib.request.Request(API+'?'+q,headers={'apikey':token,'Accept':'application/json','User-Agent':'rer-dashboard/1.0'})
    try:
        with urllib.request.urlopen(req,timeout=25) as r: data=json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 429:
            quota_headers = [f'{k}: {v}' for k,v in e.headers.items()
                             if any(marker in k.lower() for marker in ('ratelimit','quota','retry-after'))]
            detail = '; '.join(quota_headers)
            suffix = f' ({detail})' if detail else ''
            raise RuntimeError('IDFM daily request quota reached (HTTP 429)'+suffix) from e
        if e.code != 400: raise
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

def bus_departures_from_visits(visits, headsign, destination_name=None, line='325'):
    target=normalize(headsign)
    rows=[]
    for visit in visits:
        labels=normalize(' '.join((visit.get('dest',''),visit.get('direction',''),visit.get('display',''))))
        if target not in labels: continue
        rows.append({'from':visit['dep'].astimezone(PARIS).strftime('%H:%M'),'to':'','train':line,'destinationName':destination_name or headsign,'platform':'','status':visit['status']})
        if len(rows)==3: break
    return rows

def bus_departures(token, stop, headsign, now, destination_name=None):
    return bus_departures_from_visits(fetch(token,stop,now,BUS_LINE),headsign,destination_name)

def prior_schedule(path):
    try: return json.loads(path.read_text(encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError): return {}

def pair(a,b):
    result=[]; seen=set()
    for x in a:
        matches=[y for y in b if y['train']==x['train'] and y['dest']==x['dest'] and x['dep']<y['dep']<=x['dep']+timedelta(minutes=90)]
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

    old_rer_stations={s.get('id'):s for s in previous.get('rerStations',[]) if s.get('id')}
    rer_station_rows={}
    for station_id, station_name, stop_ref in RER_STATIONS:
        if station_id == 'bfm':
            station_visits=data[1]
        else:
            try:
                station_visits=fetch(token,stop_ref,now)
            except Exception as e:
                print(f'RER station refresh failed for {station_name}; retaining last available rows: {e}',file=sys.stderr)
                rer_station_rows[station_id]=old_rer_stations.get(station_id,{}).get('rows',[])
                continue
        rer_station_rows[station_id]=pair(station_visits,data[0])[:2]
    rer_stations=[{'id':station_id,'title':station_name,'rows':rer_station_rows.get(station_id,[])} for station_id,station_name,_ in RER_STATIONS]

    old_cards={c.get('card'):c for c in previous.get('cards',[]) if c.get('mode')=='bus'}
    bus_updated=dt(previous.get('busFetchedAt'))
    if bus_updated is None or now-bus_updated>=BUS_REFRESH or 'bus-125' not in old_cards or 'bus-323' not in old_cards:
        bus_complete=True
        try:
            quai_visits=fetch(token,BUS_STOPS['quai'],now,BUS_LINE)
            bus_quai=bus_departures_from_visits(quai_visits,'Quai de la Gare')
            bus_eglise=bus_departures_from_visits(quai_visits,'Château de Vincennes','Église de Saint-Mandé')
        except Exception as e:
            print('BUS 325 refresh failed; retaining the last available BUS 325 data: '+str(e),file=sys.stderr)
            bus_quai=old_cards.get('bus-quai',{}).get('rows',[])
            bus_eglise=old_cards.get('bus-eglise',{}).get('rows',[])
            bus_complete=False
        try:
            bus_vincennes=bus_departures(token,BUS_STOPS['vincennes'],'Château de Vincennes',now)
        except Exception as e:
            print('BUS 325 Vincennes refresh failed; retaining the last available data: '+str(e),file=sys.stderr)
            bus_vincennes=old_cards.get('bus-vincennes',{}).get('rows',[])
            bus_complete=False
        try:
            bus125_visits=fetch(token,BUS_STOPS['quai'],now,BUS125_LINE)
            bus_125=bus_departures_from_visits(bus125_visits,"Porte d'Orléans",'Jean Le Galleu',line='125')
            print(f"New route rows: BUS 125={len(bus_125)}")
        except Exception as e:
            print('BUS 125 refresh failed; retaining the last available data: '+str(e),file=sys.stderr)
            bus_125=old_cards.get('bus-125',{}).get('rows',[])
            bus_complete=False
        try:
            bus323_visits=fetch(token,BUS_STOPS['moliere'],now,BUS323_LINE)
            bus_323=bus_departures_from_visits(bus323_visits,'Châtillon - Montrouge - Métro','Hôpital Jean Rostand',line='323')
            print(f"New route rows: BUS 323={len(bus_323)}")
        except Exception as e:
            print('BUS 323 refresh failed; retaining the last available data: '+str(e),file=sys.stderr)
            bus_323=old_cards.get('bus-323',{}).get('rows',[])
            bus_complete=False
        if bus_complete:
            bus_updated=now
            print('Refreshed BUS 325, 125 and 323 data.')
        elif bus_updated is None:
            bus_updated=now
    else:
        bus_quai=old_cards.get('bus-quai',{}).get('rows',[])
        bus_vincennes=old_cards.get('bus-vincennes',{}).get('rows',[])
        bus_eglise=old_cards.get('bus-eglise',{}).get('rows',[])
        bus_125=old_cards.get('bus-125',{}).get('rows',[])
        bus_323=old_cards.get('bus-323',{}).get('rows',[])

    cards=[
        {'card':'rer-ivry','mode':'rer','line':'C','title':STATIONS[0][0],'destination':STATIONS[1][0],'rows':directions[0]['rows'][:2]},
        {'card':'bus-quai','mode':'bus','line':'325','title':'Jean-Jacques Rousseau','destination':'Émile Durkheim','rows':bus_quai},
        {'card':'rer-bfm','mode':'rer','line':'C','title':STATIONS[1][0],'destination':STATIONS[0][0],'rows':directions[1]['rows'][:2]},
        {'card':'bus-vincennes','mode':'bus','line':'325','title':'Bibliothèque François-Mitterrand','destination':'Jean-Jacques Rousseau','rows':bus_vincennes},
        {'card':'bus-eglise','mode':'bus','line':'325','title':'Jean-Jacques Rousseau','destination':'Église de Saint-Mandé','rows':bus_eglise},
        {'card':'bus-125','mode':'bus','line':'125','title':'Jean-Jacques Rousseau','destination':'Jean Le Galleu','rows':bus_125},
        {'card':'bus-323','mode':'bus','line':'323','title':'Molière','destination':'Hôpital Jean Rostand','rows':bus_323}
    ]
    stamp=now.astimezone(PARIS).strftime('%d.%m.%Y, %H:%M:%S')
    out={'fetchedAtParis':stamp,'directions':directions,'cards':cards,'rerStations':rer_stations,'busFetchedAt':bus_updated.isoformat().replace('+00:00','Z') if bus_updated else None,'busFetchedAtParis':bus_updated.astimezone(PARIS).strftime('%d.%m.%Y, %H:%M:%S') if bus_updated else None}
    schedule_path.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Updated schedule.json at '+stamp+' Paris time')
if __name__=='__main__':
    try: main()
    except Exception as e: print('Schedule update failed: '+str(e),file=sys.stderr); raise
