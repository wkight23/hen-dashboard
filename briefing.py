import os, json, requests
from datetime import datetime, date

ERCOT_USER = os.environ['ERCOT_USERNAME']
ERCOT_PASS = os.environ['ERCOT_PASSWORD']
ERCOT_SUBKEY = os.environ['ERCOT_SUBKEY']
ANTHROPIC_KEY = os.environ['ANTHROPIC_API_KEY']

BASE = 'https://api.ercot.com/api/public-reports'
AUTH_URL = 'https://ercotb2c.b2clogin.com/ercotb2c.onmicrosoft.com/B2C_1_PUBAPI-ROPC-FLOW/oauth2/v2.0/token'
TODAY = date.today().isoformat()
NOW = datetime.now()
MODE = 'da' if NOW.hour >= 13 else 'morning'

print("Authenticating with ERCOT...")
auth_resp = requests.post(AUTH_URL, data={
    'username': ERCOT_USER, 'password': ERCOT_PASS,
    'grant_type': 'password',
    'scope': 'openid fec253ea-0d06-4272-a5e6-b478baeecd70 offline_access',
    'client_id': 'fec253ea-0d06-4272-a5e6-b478baeecd70',
    'response_type': 'id_token'
})
token = auth_resp.json().get('id_token', '')
hdrs = {'Authorization': f'Bearer {token}', 'Ocp-Apim-Subscription-Key': ERCOT_SUBKEY}

print("Fetching ERCOT data...")
def eg(path):
    try:
        r = requests.get(f'{BASE}/{path}?deliveryDateFrom={TODAY}&deliveryDateTo={TODAY}&size=500', headers=hdrs, timeout=30)
        return r.json() if r.ok else {}
    except:
        return {}

wind_data = eg('np4-742-cd/wpp_hrly_actual_fcast_geo')
load_data = eg('np3-565-cd/lf_by_model_weather_zone')
solar_data = eg('np4-737-cd/spp_hrly_avrg_actl_fcast')
shadow_data = eg('np4-191-cd/dam_shadow_prices') if MODE == 'da' else {}

def avg(lst): return sum(lst)/len(lst)/1000 if lst else 0
def mx(lst): return max(lst)/1000 if lst else 0

items = wind_data.get('_embedded', {}).get('wpp_hrly_actual_fcast_geo', wind_data.get('data', []))
br = {'WEST': [], 'SOUTH': [], 'COASTAL': [], 'PANHANDLE': []}
for r in items:
    rg = (r.get('genRegion') or r.get('region') or '').upper()
    v = float(r.get('hourlyWindGenForecast') or r.get('genForecast') or 0)
    if rg in br and v > 0: br[rg].append(v)
wind = {k.lower(): avg(br[k.upper()]) for k in ['west','south','coastal','pan']}
wind['pan'] = avg(br['PANHANDLE'])
wind['total'] = sum(wind.values())
sol = solar_data.get('_embedded', {}).get('spp_hrly_avrg_actl_fcast', solar_data.get('data', []))
sv = [float(r.get('hourlySystemGenForecast') or 0) for r in sol if float(r.get('hourlySystemGenForecast') or 0) > 0]
wind['solar'] = max(sv)/1000 if sv else 0

li = load_data.get('_embedded', {}).get('lf_by_model_weather_zone', load_data.get('data', []))
bz = {'WEST': [], 'SOUTH': [], 'NORTH': [], 'HOUSTON': []}
for r in li:
    z = (r.get('weatherZone') or r.get('zone') or '').upper().replace('LZ_', '')
    v = float(r.get('systemTotal') or r.get('loadForecast') or r.get('totalLoad') or 0)
    if z in bz and v > 0: bz[z].append(v)
load = {'west': mx(bz['WEST']), 'south': mx(bz['SOUTH']), 'north': mx(bz['NORTH']), 'houston': mx(bz['HOUSTON'])}
load['total'] = sum(load.values())

si = shadow_data.get('_embedded', {}).get('dam_shadow_prices', shadow_data.get('data', []))
sc = {}
for r in si:
    nm = r.get('constraintName') or r.get('name') or 'Unknown'
    sp = abs(float(r.get('shadowPrice') or 0))
    he = int(r.get('deliveryHour') or 0)
    if nm not in sc: sc[nm] = {'sps': [], 'hrs': []}
    if sp > 0.01: sc[nm]['sps'].append(sp); sc[nm]['hrs'].append(he)
shadow_list = sorted([{'name':k,'maxSP':max(v['sps']),'hours':sorted(set(v['hrs'])),'cnt':len(v['sps'])} for k,v in sc.items() if v['sps']], key=lambda x:-x['maxSP'])[:15]

season = {1:'Winter',2:'Winter',3:'Spring',4:'Spring',5:'Spring',6:'Summer',7:'Summer',8:'Summer',9:'Fall',10:'Fall',11:'Fall',12:'Winter'}[NOW.month]

PLAYBOOK = """TWINBU-HARGROVE 138KV [ACTIVE] Season:Summer+Winter PeakHE:HE5,6,4 Driver:West wind sub 5GW. Also up to sub 8GW. Nodes:Russek(+31.7%),Hamilton(+6.8%),FortDuncan(+4.4%)
LARDVNTH-LASCRUCE 138KV [ACTIVE] Season:Summer PeakHE:HE20,21,22 Driver:South wind 2GW+ AND coastal wind 2GW+. Nodes:Holcomb(+29.7%),Catarina(+17.9%),ValVerde(-7.9%)
FORTMA-YELWJCKT 138KV [ACTIVE] Season:All PeakHE:HE21,20,23 Driver:West wind below 3GW overnight. Nodes:Junction(+50%),Russek(+3.2%)
STP-ELMCREEK 345KV [ACTIVE] Season:Nov-Jan PeakHE:HE22,21,23 Driver:Low renewable overnight sub 8GW total wind. Nodes:Catarina(+8%),Holcomb(+7.9%),Mainland(-9%)
TREADWEL-YELWJCKT 138KV [ACTIVE] Season:Summer PeakHE:HE17,18,19 Driver:West load 9GW+. Nodes:Junction(+46.8%)
LASCRUCE-MILO 138KV [ACTIVE] Season:Winter PeakHE:HE20,19,21 Driver:South AND coastal wind both 2GW+. Nodes:Holcomb(+28%),Catarina(+17.3%)
WESTEX [ACTIVE] Season:All PeakHE:HE20,19,12 Driver:High renewable or west gen above 15GW overnight. Nodes:Diboll(+19.4%),Judkins(-71.8%),Russek(-66%)
LNGSW-PRLSW 345KV [ACTIVE] Season:All PeakHE:HE1,2,24 Driver:West wind above 10GW overnight. Nodes:Judkins(+21.3%),Saddleback(+20.4%),Russek(+7%)
E_PASP [ACTIVE] Season:All PeakHE:HE20,19,18 Driver:South load 18GW+ during down ramps. Nodes:Junction(+4%),ValVerde(-19.6%),Holcomb(-13.8%)
NLARSW-PILONCIL 138KV [ACTIVE] Season:All PeakHE:HE24,1,2 Driver:Coastal wind 2.5GW+ or south wind 2.5GW+. Nodes:Catarina(+26%),FortDuncan(+12%)
MGSW-CATSW 345KV [ACTIVE] Season:All PeakHE:HE23,19,20 Driver:West load 9GW+ with wind sub 8GW. Nodes:Judkins(+30%),Saddleback(+27%),Russek(+10%)
LOBO-LARDVNTH 138KV [ACTIVE] Season:Feb-Mar PeakHE:HE22,19,21 Driver:South wind 2.5GW+ or coastal 2.8GW+. Nodes:Holcomb(+32.4%),Catarina(+21.8%)
ESCONDID-GANSO 138KV [ACTIVE] Season:All PeakHE:HE8,9,1 Driver:West wind sub 3GW plus west load 9GW+. Nodes:Hamilton(+40.4%),FortDuncan(-26.1%)
BCESW-SNDSW 345KV [ACTIVE] Season:Fall/Spring PeakHE:HE17,18,16 Driver:South wind sub 1GW south load 15GW+. Nodes:Holcomb(+11%),ValVerde(+11%)
LNGSW-CONSW 345KV [ACTIVE] Season:Summer PeakHE:HE1,2,24 Driver:West wind 10GW+ west load 9GW+ overnight. Nodes:Judkins(+21.3%),Saddleback(+20%),Russek(+8%)
YELWJCKT-FORTMA 138KV [ACTIVE] Season:Spring/Summer PeakHE:HE7,6,5 Driver:West winds 13GW+ offpeak 10GW+ onpeak. Nodes:Junction(-50%)
ASHERTON-CATARINA 138KV [WATCH] Season:Summer PeakHE:HE13,12,14 Driver:Very low coastal AND south wind during solar window. Nodes:Catarina(+77%)
MRVLY-ESTLD 69KV [WATCH] Season:Not seasonal PeakHE:HE20,19,21 Driver:North load above 15GW. Nodes:Cisco(+17.3%)
STP-WAP 345KV [WATCH] Season:Summer PeakHE:HE17,16,13 Driver:Houston load 18GW+. Nodes:Mainland(+9.6%)
PALOUSE-WOLFCAMP 138KV [WATCH] Season:All PeakHE:HE18,17,16 Driver:West load 9GW+ during solar ramp-down. Nodes:Russek(+30.6%)
CRDCW-OLNEY 69KV [WATCH] Season:Spring/Summer PeakHE:HE17,18,16 Driver:North load 22GW+ DFW heat 6630_A_LN outage. Nodes:Olney(+78.7%)
CARVER-TINSLEY 138KV [WATCH] Season:All PeakHE:HE21,20,22 Driver:West wind 10GW+ with coastal wind sub 2GW. Nodes:Hamilton(+32.3%),FortDuncan(+21%)
MAXWELL-HAMILTON 138KV [WATCH] Season:Summer/Fall PeakHE:HE2,24,1 Driver:West wind 13GW+. Nodes:Hamilton(+23%),FortDuncan(+14.3%)
MASN-KATEMCY 69KV [WATCH] Season:Winter PeakHE:HE19,18,23 Driver:Low west wind low north wind. Nodes:Junction(+25.1%)
PRSLW-CONSW 345KV [WATCH] Season:Winter/Spring PeakHE:HE2,4,1 Driver:Mild temps lower loads west wind 8GW+. Nodes:Judkins(+29%),Saddleback(+23.4%)
SONR-ATSO 69KV [WATCH] Season:All PeakHE:HE1,3,2 Driver:West load 9GW+ overnight. Nodes:Russek(+5%)"""

sp_str = ''
if shadow_list:
    sp_str = 'ERCOT DAM SHADOW PRICES:
' + '
'.join([f"  {c['name']}: max ${c['maxSP']:.0f}/MWh, HE {','.join(map(str,c['hours'][:3]))}" for c in shadow_list])

user_msg = f"""{'Morning' if MODE=='morning' else 'DA'} briefing {TODAY} ({season})
West wind:{wind['west']:.1f}GW South:{wind['south']:.1f}GW Coastal:{wind['coastal']:.1f}GW Pan:{wind['pan']:.1f}GW Total:{wind['total']:.1f}GW Solar:{wind['solar']:.1f}GW
West load:{load['west']:.1f}GW South:{load['south']:.1f}GW North:{load['north']:.1f}GW Houston:{load['houston']:.1f}GW Total:{load['total']:.1f}GW
{sp_str}
Which constraints activate today?"""

sys_msg = f"""You are HEN NOC Constraint Analyst. PLAYBOOK:
{PLAYBOOK}
RULES: ASCII only. No curly quotes. No em-dashes. No newlines in strings. No apostrophes - write cannot not cant.
Return ONLY valid JSON: {{"summary":"text","riskLevel":"HIGH or MODERATE or LOW","highConfidence":[{{"name":"x","priority":"ACTIVE or WATCH","likelyHours":"HE x","driver":"text","nodes":["x"],"season":"x","confidence":"HIGH or MEDIUM"}}],"watchList":[same],"unlikely":["x"],"operatorNote":"text"}}"""

print("Calling Claude...")
cr = requests.post('https://api.anthropic.com/v1/messages',
    headers={'Content-Type':'application/json','x-api-key':ANTHROPIC_KEY,'anthropic-version':'2023-06-01'},
    json={'model':'claude-sonnet-4-6','max_tokens':1500,'system':sys_msg,'messages':[{'role':'user','content':user_msg}]},
    timeout=60)
raw = cr.json()['content'][0]['text']
result = json.loads(raw[raw.index('{'):raw.rindex('}')+1])

high = result.get('highConfidence', [])
watch = result.get('watchList', [])
unlikely = result.get('unlikely', [])
risk = result.get('riskLevel', 'MODERATE')
rc = '#c0392b' if risk=='HIGH' else '#9a6200' if risk=='MODERATE' else '#1d6b3e'

def chtml(c, col):
    nodes = ''.join([f'<span style="font-size:10px;padding:2px 6px;border-radius:3px;background:rgba(75,172,198,0.1);color:#4BACC6;font-family:monospace;margin-right:4px">{n}</span>' for n in c.get('nodes',[])])
    return f'''<div style="border-left:3px solid {col};padding:12px 14px;margin-bottom:8px;background:#111f30;border-radius:0 6px 6px 0">
<div style="display:flex;justify-content:space-between;margin-bottom:4px">
<strong style="font-size:13px;color:#e8f4f8">{"🟢" if c.get("priority")=="ACTIVE" else "🟡"} {c.get("name","")}</strong>
<span style="font-size:10px;font-weight:700;padding:2px 8px;border-radius:3px;background:rgba(224,82,82,0.1);color:{col}">{c.get("confidence","")}</span>
</div>
<div style="font-size:11px;color:#7ea8bc;margin-bottom:4px">{c.get("likelyHours","")} · {c.get("season","")}</div>
<div style="font-size:12px;color:#a0b8c8;margin-bottom:6px">{c.get("driver","")}</div>
<div>{nodes}</div>
</div>'''

def gcell(label, val, warn=False, alert=False):
    col = "#c0392b" if alert else "#9a6200" if warn else "#e8f4f8"
    bg = "rgba(224,82,82,0.07)" if alert else "rgba(212,135,42,0.07)" if warn else "#111f30"
    return f'<div style="background:{bg};border-radius:6px;padding:10px 12px"><div style="font-size:9px;font-weight:600;text-transform:uppercase;letter-spacing:0.06em;color:#3d6478;margin-bottom:4px">{label}</div><div style="font-size:20px;font-weight:600;color:{col};font-family:monospace">{val}</div></div>'

sp_tbl = ""
if shadow_list:
    rows = "".join([f'<tr><td style="padding:6px 8px;font-size:11px;color:#e8f4f8;border-bottom:1px solid rgba(255,255,255,0.05)">{c["name"]}</td><td style="padding:6px 8px;font-size:12px;font-weight:600;color:{"#f28b82" if c["maxSP"]>200 else "#f5c842" if c["maxSP"]>50 else "#5db87a"};border-bottom:1px solid rgba(255,255,255,0.05)">${c["maxSP"]:.0f}</td><td style="padding:6px 8px;font-size:11px;color:#7ea8bc;border-bottom:1px solid rgba(255,255,255,0.05)">HE {",".join(map(str,c["hours"][:3]))}</td></tr>' for c in shadow_list[:10]])
    sp_tbl = f'''<div style="background:#0d1825;border:0.5px solid rgba(75,172,198,0.12);border-radius:10px;padding:1.25rem;margin-bottom:1rem">
<div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.07em;color:#4BACC6;margin-bottom:10px">ERCOT DAM Shadow Prices</div>
<table style="width:100%;border-collapse:collapse">
<thead><tr><th style="text-align:left;font-size:10px;color:#3d6478;padding:0 8px 6px;border-bottom:1px solid rgba(255,255,255,0.05)">Constraint</th><th style="text-align:left;font-size:10px;color:#3d6478;padding:0 8px 6px;border-bottom:1px solid rgba(255,255,255,0.05)">Max SP</th><th style="text-align:left;font-size:10px;color:#3d6478;padding:0 8px 6px;border-bottom:1px solid rgba(255,255,255,0.05)">Peak hrs</th></tr></thead>
<tbody>{rows}</tbody></table></div>'''

html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>HEN Briefing {TODAY}</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;background:#070f1a;color:#e8f4f8;min-height:100vh}}.g6{{display:grid;grid-template-columns:repeat(6,1fr);gap:8px}}</style>
</head><body>
<div style="background:#022a4e;border-bottom:1px solid rgba(75,172,198,0.25);padding:0 1.5rem;height:52px;display:flex;align-items:center;justify-content:space-between">
<div style="display:flex;align-items:center;gap:10px"><div style="width:28px;height:28px;background:#4BACC6;border-radius:5px;display:flex;align-items:center;justify-content:center"><svg fill="white" width="16" height="16" viewBox="0 0 24 24"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg></div><strong>HEN Congestion Dashboard</strong></div>
<div style="display:flex;align-items:center;gap:10px"><span style="font-size:11px;color:#4BACC6;background:rgba(75,172,198,0.1);border:1px solid rgba(75,172,198,0.25);padding:3px 10px;border-radius:4px;font-family:monospace">{TODAY} {"Morning" if MODE=="morning" else "DA 12:45+"}</span><span style="font-size:10px;font-weight:700;padding:3px 9px;border-radius:4px;background:{rc};color:white">{risk}</span></div>
</div>
<div style="max-width:900px;margin:0 auto;padding:1.5rem">
<div style="background:#0d1825;border:0.5px solid rgba(75,172,198,0.12);border-radius:10px;padding:1.25rem;margin-bottom:1rem">
<div style="font-size:13px;color:#a0c8d8;line-height:1.5;margin-bottom:1rem">{result.get("summary","")}</div>
<div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.07em;color:#4BACC6;margin-bottom:0.875rem;display:flex;align-items:center;gap:7px"><span style="display:block;width:3px;height:14px;background:#4BACC6;border-radius:2px"></span>Wind generation forecast</div>
<div class="g6" style="margin-bottom:1rem">
{gcell("West wind",f"{wind['west']:.1f} GW",wind['west']<5,wind['west']<2)}
{gcell("South wind",f"{wind['south']:.1f} GW",wind['south']>1.5,wind['south']>2.5)}
{gcell("Coastal wind",f"{wind['coastal']:.1f} GW",wind['coastal']>1.5,wind['coastal']>2.5)}
{gcell("Panhandle",f"{wind['pan']:.1f} GW")}
{gcell("Total wind",f"{wind['total']:.1f} GW",wind['total']<5 or wind['total']>12,wind['total']<2)}
{gcell("Solar",f"{wind['solar']:.1f} GW")}
</div>
<div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.07em;color:#4BACC6;margin-bottom:0.875rem;display:flex;align-items:center;gap:7px"><span style="display:block;width:3px;height:14px;background:#4BACC6;border-radius:2px"></span>Load forecast by zone</div>
<div class="g6">
{gcell("West zone",f"{load['west']:.1f} GW",load['west']>=8.5,load['west']>=9.5)}
{gcell("South zone",f"{load['south']:.1f} GW",load['south']>=16,load['south']>=18)}
{gcell("North zone",f"{load['north']:.1f} GW",load['north']>=20,load['north']>=22)}
{gcell("Houston zone",f"{load['houston']:.1f} GW",load['houston']>=16,load['houston']>=18)}
{gcell("ERCOT total",f"{load['total']:.1f} GW")}
{gcell("Generated",NOW.strftime("%H:%M CDT"))}
</div>
</div>
{sp_tbl}
{"<div style=\"background:#0d1825;border:0.5px solid rgba(75,172,198,0.12);border-radius:10px;padding:1.25rem;margin-bottom:1rem\"><div style=\"font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.07em;color:#c0392b;margin-bottom:0.875rem\">High-probability constraints</div>" + "".join([chtml(c,"#c0392b") for c in high]) + "</div>" if high else ""}
{"<div style=\"background:#0d1825;border:0.5px solid rgba(75,172,198,0.12);border-radius:10px;padding:1.25rem;margin-bottom:1rem\"><div style=\"font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.07em;color:#4BACC6;margin-bottom:0.875rem\">Watch list</div>" + "".join([chtml(c,"#4BACC6") for c in watch]) + "</div>" if watch else ""}
{'<div style="background:#0d1825;border:0.5px solid rgba(75,172,198,0.12);border-radius:10px;padding:1.25rem;margin-bottom:1rem"><div style="font-size:11px;font-weight:600;text-transform:uppercase;color:#9a6200;margin-bottom:6px">Operator note</div><div style="font-size:12px;color:#c8b87a;padding:10px 12px;background:rgba(212,135,42,0.07);border-left:3px solid #9a6200;border-radius:0 4px 4px 0">' + result.get("operatorNote","") + '</div></div>' if result.get("operatorNote") else ""}
{'<div style="background:#0a1220;border:0.5px solid rgba(75,172,198,0.08);border-radius:10px;padding:1rem"><div style="font-size:10px;font-weight:600;text-transform:uppercase;color:#3d6478;margin-bottom:6px">Low probability today</div><div style="font-size:11px;color:#3d6478">' + " &nbsp;·&nbsp; ".join(unlikely) + '</div></div>' if unlikely else ""}
</div></body></html>"""

with open('results.html', 'w') as f:
    f.write(html)
print(f"Done. Mode:{MODE} Risk:{risk} High:{len(high)} Watch:{len(watch)}")
