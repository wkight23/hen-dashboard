import os, json, requests, re, time
from datetime import datetime, date, timedelta, timezone

ERCOT_USER = os.environ["ERCOT_USERNAME"]
ERCOT_PASS = os.environ["ERCOT_PASSWORD"]
ERCOT_SUBKEY = os.environ["ERCOT_SUBKEY"]
ANTHROPIC_KEY = os.environ["ANTHROPIC_API_KEY"]
BASE = "https://api.ercot.com/api/public-reports"
AUTH_URL = "https://ercotb2c.b2clogin.com/ercotb2c.onmicrosoft.com/B2C_1_PUBAPI-ROPC-FLOW/oauth2/v2.0/token"
TODAY = date.today().isoformat()
YESTERDAY = (date.today() - timedelta(days=1)).isoformat()
TOMORROW = (date.today() + timedelta(days=1)).isoformat()
NOW = datetime.now()
CDT = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=5)
SOLAR_HE = set(range(9, 15))

SITE_ZONES = {"RUSSEKST_RN":"WEST","JUNCTION_RN":"WEST","OLNEYTN_RN":"WEST","GRDNE_ESR_RN":"WEST","JDKNS_RN":"WEST","LONESTAR_RN":"WEST","RTLSNAKE_BT":"WEST","SANDLAKE_RN":"WEST","CEDRVALE_RN":"WEST","COYOTSPR_RN":"WEST","FAULKNER_RN":"WEST","SADLBACK_RN":"WEST","TOYAH_RN":"WEST","GOMZ_RN":"WEST","SBEAN_BESS":"WEST","HAMI_BESS_RN":"SOUTH","FTDUNCAN_RN":"SOUTH","CATARINA_B1":"SOUTH","HOLCOMB_RN1":"SOUTH","POTEETS_RN":"SOUTH","FALFUR_RN":"SOUTH","MV_VALV4_RN":"SOUTH","TYNAN_RN":"SOUTH","WLTC_ESR_RN":"SOUTH","PAVLOV_BT_RN":"SOUTH","MAINLAND_RN":"HOUSTON","DIBOL_RN":"NORTH","PAULN_RN":"NORTH","FRMRSVLW_RN":"NORTH","MNWL_BESS_RN":"NORTH","CISC_RN":"NORTH","LFSTH_RN":"NORTH"}
SITE_NAMES = {"RUSSEKST_RN":"Russek","JUNCTION_RN":"Junction","OLNEYTN_RN":"Olney","GRDNE_ESR_RN":"Garden City","JDKNS_RN":"Judkins","LONESTAR_RN":"Lonestar","RTLSNAKE_BT":"Rattlesnake","SANDLAKE_RN":"Sandlake","CEDRVALE_RN":"Cedarvale","COYOTSPR_RN":"Coyote","FAULKNER_RN":"Faulkner","SADLBACK_RN":"Saddleback","TOYAH_RN":"Toyah","GOMZ_RN":"Gomez","SBEAN_BESS":"Screwbean","HAMI_BESS_RN":"Hamilton","FTDUNCAN_RN":"Fort Duncan","CATARINA_B1":"Catarina","HOLCOMB_RN1":"Holcomb","POTEETS_RN":"Poteets","FALFUR_RN":"Falfurrias","MV_VALV4_RN":"Val Verde","TYNAN_RN":"Tynan","WLTC_ESR_RN":"Weil Tract","PAVLOV_BT_RN":"Pavlov","MAINLAND_RN":"Mainland","DIBOL_RN":"Diboll","PAULN_RN":"Pauline","FRMRSVLW_RN":"Farmersville","MNWL_BESS_RN":"Mineral Wells","CISC_RN":"Cisco","LFSTH_RN":"Lufkin South"}
ZONE_HUBS = {"WEST":"LZ_WEST","SOUTH":"LZ_SOUTH","NORTH":"LZ_NORTH","HOUSTON":"LZ_HOUSTON"}
SF_TO_SP = {'Russek':'RUSSEKST_RN','Catarina':'CATARINA_B1','Holcomb':'HOLCOMB_RN1','Hamilton':'HAMI_BESS_RN','FortDuncan':'FTDUNCAN_RN','Junction':'JUNCTION_RN','Judkins':'JDKNS_RN','Saddleback':'SADLBACK_RN','Cedarvale':'CEDRVALE_RN','Toyah':'TOYAH_RN','Coyote':'COYOTSPR_RN','Faulkner':'FAULKNER_RN','GardenCity':'GRDNE_ESR_RN','Gomez':'GOMZ_RN','Lonestar':'LONESTAR_RN','Rattlesnake':'RTLSNAKE_BT','Sandlake':'SANDLAKE_RN','Screwbean':'SBEAN_BESS','ValVerde':'MV_VALV4_RN','Falfurrias':'FALFUR_RN','Pavlov':'PAVLOV_BT_RN','Poteets':'POTEETS_RN','Tynan':'TYNAN_RN','WeilTract':'WLTC_ESR_RN','Mainland':'MAINLAND_RN','Cisco':'CISC_RN','Diboll':'DIBOL_RN','Farmersville':'FRMRSVLW_RN','LufkinSouth':'LFSTH_RN','MineralWells':'MNWL_BESS_RN','Olney':'OLNEYTN_RN','Pauline':'PAULN_RN'}

# Authenticate
print("Authenticating...")
auth_resp = requests.post(AUTH_URL, data={"username":ERCOT_USER,"password":ERCOT_PASS,"grant_type":"password","scope":"openid fec253ea-0d06-4272-a5e6-b478baeecd70 offline_access","client_id":"fec253ea-0d06-4272-a5e6-b478baeecd70","response_type":"id_token"})
token = auth_resp.json().get("id_token","")
hdrs = {"Authorization":"Bearer "+token,"Ocp-Apim-Subscription-Key":ERCOT_SUBKEY}

def parse_he(val):
    try:
        s = str(val)
        if ":" in s: return int(s.split(":")[0])
        return int(float(s))
    except: return 0

# ─── 1. SCED Shadow Prices (yesterday - full day binding constraints) ───
print("Fetching SCED constraints...")
sced_rows = []
for page in range(1, 5):
    try:
        ts_from = YESTERDAY + "T00:00:00"
        ts_to = YESTERDAY + "T23:59:59"
        r = requests.get(BASE+"/np6-86-cd/shdw_prices_bnd_trns_const",
            params={"SCEDTimestampFrom":ts_from,"SCEDTimestampTo":ts_to,"page":page,"size":5000},
            headers=hdrs, timeout=30)
        if r.ok:
            d = r.json()
            rows = d.get("data",[])
            sced_rows.extend(rows)
            if len(rows) < 5000: break
        else:
            break
    except: break
print(f"SCED rows: {len(sced_rows)}")

# Parse SCED constraints
# [0]=SCEDTimestamp [3]=constraintName [4]=contingencyName [5]=shadowPrice [6]=maxShadowPrice [9]=violatedMW [10]=fromStation [11]=toStation
constraints = {}
for row in sced_rows:
    if not isinstance(row, list) or len(row) < 12: continue
    try:
        sp = float(row[5]) if row[5] else 0
        if sp <= 0: continue
        name = str(row[3]).strip() if row[3] else "Unknown"
        ts = str(row[0]) if row[0] else ""
        he = 0
        if "T" in ts:
            try: he = int(ts.split("T")[1].split(":")[0]) + 1
            except: he = 0
        from_st = str(row[10]).strip() if row[10] else ""
        to_st = str(row[11]).strip() if row[11] else ""
        if name not in constraints:
            constraints[name] = {"shadow_prices":[],"hours":set(),"from_st":from_st,"to_st":to_st,"violated_mw":[]}
        constraints[name]["shadow_prices"].append(sp)
        constraints[name]["hours"].add(he)
        try:
            viol = float(row[9]) if row[9] else 0
            if viol > 0: constraints[name]["violated_mw"].append(viol)
        except: pass
    except: continue

# Build constraint summary with MCC
constraint_list = []
for name, data in constraints.items():
    sps = data["shadow_prices"]
    avg_sp = sum(sps)/len(sps)
    max_sp = max(sps)
    hours = sorted(data["hours"])
    # Find matching SF data
    node_mcc = {}
    # Try exact match then fuzzy on from/to station
    sf_entry = None
    for sf_name, sf_data in SF_TO_SP.items():
        pass  # will do lookup below
    # Look up in our constraint name lookup
    from_tok = data["from_st"].upper().replace(" ","").replace("-","")
    to_tok = data["to_st"].upper().replace(" ","").replace("-","")
    best_sf = {}
    # Try to match constraint name against our SF_DATA keys
    name_upper = name.upper()
    # Simple token match
    for sf_key in SF_TO_SP.keys():
        sp_node = SF_TO_SP[sf_key]
        # We'll compute MCC using avg shadow price if we find the constraint
    # For now use name-based lookup from a simple embedded map
    constraint_list.append({
        "name": name,
        "avg_sp": round(avg_sp, 2),
        "max_sp": round(max_sp, 2),
        "hours_binding": len(sps),
        "peak_hours": hours[:5],
        "from_st": data["from_st"],
        "to_st": data["to_st"],
    })

# Sort by avg_sp * hours_binding
constraint_list.sort(key=lambda x: -(x["avg_sp"] * x["hours_binding"]))
top_constraints = constraint_list[:15]

# ─── 2. RT Settlement Point Prices (current hour) ───
print("Fetching RT prices...")
rt_prices = {}
KEY_NODES = list(ZONE_HUBS.values()) + ["JDKNS_RN","SADLBACK_RN","CEDRVALE_RN","RUSSEKST_RN","CATARINA_B1","HOLCOMB_RN1","HAMI_BESS_RN","JUNCTION_RN","MV_VALV4_RN","FALFUR_RN","TOYAH_RN","GOMZ_RN","LONESTAR_RN"]
for node in KEY_NODES:
    try:
        r = requests.get(BASE+"/np6-905-cd/spp_node_zone_hub",
            params={"settlementPoint":node,"deliveryDateFrom":TODAY,"deliveryDateTo":TODAY,"size":100},
            headers=hdrs, timeout=15)
        if r.ok:
            d = r.json()
            fields = d.get("fields",[])
            rows = d.get("data",[])
            he_col = next((f["cardinality"]-1 for f in fields if "hour" in f.get("name","").lower()),2)
            pr_col = next((f["cardinality"]-1 for f in fields if "price" in f.get("name","").lower() or "Price" in f.get("name","")),3)
            if rows:
                # Get most recent interval
                latest = rows[-1]
                if isinstance(latest, list) and len(latest) > pr_col:
                    try:
                        price = float(latest[pr_col])
                        rt_prices[node] = round(price, 2)
                    except: pass
    except: pass
    time.sleep(0.2)
print(f"RT prices: {len(rt_prices)} nodes")

# ─── 3. DA Prices for tomorrow (solar window focus) ───
print("Fetching DA prices for tomorrow...")
da_prices = {}
for node in KEY_NODES:
    try:
        r = requests.get(BASE+"/np4-190-cd/dam_stlmnt_pnt_prices",
            params={"settlementPoint":node,"deliveryDateFrom":TOMORROW,"deliveryDateTo":TOMORROW,"size":25},
            headers=hdrs, timeout=15)
        if r.ok:
            d = r.json()
            fields = d.get("fields",[])
            rows = d.get("data",[])
            he_col = next((f["cardinality"]-1 for f in fields if "hour" in f.get("name","").lower()),2)
            pr_col = next((f["cardinality"]-1 for f in fields if "Price" in f.get("name","")),4)
            for row in rows:
                if not isinstance(row, list): continue
                he = parse_he(row[he_col]) if he_col < len(row) else 0
                try:
                    price = float(row[pr_col]) if pr_col < len(row) and row[pr_col] else 0
                    if node not in da_prices: da_prices[node] = {}
                    da_prices[node][he] = round(price, 2)
                except: pass
    except: pass
    time.sleep(0.2)
print(f"DA prices: {len(da_prices)} nodes")

# ─── 4. Compute RT vs DA comparison ───
rt_vs_da = {}
for zone, hub in ZONE_HUBS.items():
    rt_hub = rt_prices.get(hub)
    da_hub = da_prices.get(hub, {})
    solar_da_avg = None
    if da_hub:
        solar_prices = [da_hub[he] for he in SOLAR_HE if he in da_hub]
        if solar_prices: solar_da_avg = round(sum(solar_prices)/len(solar_prices), 2)
    peak_da_he = max(da_hub, key=da_hub.get) if da_hub else None
    peak_da_price = da_hub.get(peak_da_he) if peak_da_he else None
    rt_vs_da[zone] = {
        "rt_now": rt_hub,
        "da_solar_avg": solar_da_avg,
        "da_peak_he": peak_da_he,
        "da_peak_price": peak_da_price,
        "signal": "HOLD" if (rt_hub and peak_da_price and peak_da_price > rt_hub * 1.2) else "DISPATCH" if (rt_hub and rt_hub > 50) else "MONITOR"
    }

# ─── 5. Build constraint-to-HEN-site MCC mapping ───
hen_exposure = {}
for c in top_constraints:
    cname = c["name"]
    for sf_name, sp_node in SF_TO_SP.items():
        # Simple name matching
        cname_clean = cname.upper().replace(" ","").replace("-","").replace("_","")
        # Look for matching constraint in our data (we'll use station matching)
        from_clean = c["from_st"].upper().replace(" ","")
        to_clean = c["to_st"].upper().replace(" ","")
        # This is a best-effort match - constraints tab will show raw data
    c["hen_sites"] = []

# ─── 6. Build prompt for Claude ───
print("Calling Claude for RT analysis...")
cur_he = CDT.hour + 1
remaining_he_today = list(range(cur_he+1, 25))
solar_he_tmrw = [9,10,11,12,13,14]

prompt_data = f"HEN RT Dispatch Analysis - {TODAY} {CDT.strftime('%H:%M CDT')}\n"
prompt_data += f"Current HE: {cur_he}\n\n"

prompt_data += "=== CURRENT RT LMPs ===\n"
for zone, hub in ZONE_HUBS.items():
    rt = rt_prices.get(hub, "N/A")
    prompt_data += f"{zone} ({hub}): ${rt}/MWh\n"

prompt_data += "\n=== TOMORROW DA PRICES - SOLAR WINDOW (HE9-14) ===\n"
for zone, hub in ZONE_HUBS.items():
    da_hub = da_prices.get(hub, {})
    solar = {he: da_hub[he] for he in solar_he_tmrw if he in da_hub}
    if solar:
        avg = round(sum(solar.values())/len(solar), 2)
        peak_he = max(solar, key=solar.get)
        prompt_data += f"{zone}: Solar avg ${avg}/MWh, peak HE{peak_he} ${solar[peak_he]}/MWh\n"
    else:
        prompt_data += f"{zone}: No DA data\n"

prompt_data += "\n=== TOMORROW DA PRICES - FULL DAY ===\n"
for zone, hub in ZONE_HUBS.items():
    da_hub = da_prices.get(hub, {})
    if da_hub:
        sorted_he = sorted(da_hub.items())
        prices_str = " ".join([f"HE{he}:${p}" for he,p in sorted_he])
        prompt_data += f"{zone}: {prices_str}\n"

prompt_data += "\n=== YESTERDAY SCED BINDING CONSTRAINTS (Top 10 by impact) ===\n"
for c in top_constraints[:10]:
    prompt_data += f"{c['name']}: avg ${c['avg_sp']}/MWh max ${c['max_sp']}/MWh, {c['hours_binding']} intervals, peak HEs {c['peak_hours'][:3]}\n"

prompt_data += "\n=== RT vs DA ZONE SIGNALS ===\n"
for zone, data in rt_vs_da.items():
    prompt_data += f"{zone}: RT now ${data['rt_now']}/MWh | DA solar avg ${data['da_solar_avg']}/MWh | DA peak HE{data['da_peak_he']} ${data['da_peak_price']}/MWh | Signal: {data['signal']}\n"

sys_msg = """You are a real-time dispatch analyst for Hunt Energy Network (HEN), a 32-site battery storage operator in ERCOT.

CRITICAL FRAMING RULES:
- Negative DART (DA < RT) means RT exceeded DA — FAVORABLE for RT-dispatched batteries, not underperformance
- Positive SF x positive shadow price = congestion BENEFIT at that node (LMP pushed higher, good for discharge)
- Negative SF x positive shadow price = congestion COST at that node (LMP pushed lower, charging opportunity)
- WESTEX constraint: West TX sites (Judkins/Saddleback/Cedarvale/etc) have SF ~ -0.71, so when WESTEX binds, those sites see near-zero or negative LMP — CHARGE don't dispatch
- MCC threshold: >$10/MWh on a HEN node is commercially significant

Answer three questions clearly:
1. WHAT IS HAPPENING RIGHT NOW — Are current RT prices favorable for dispatch? Which zones?
2. WHAT TO EXPECT LATER TODAY/TONIGHT — Based on yesterday's constraint patterns and current RT, what should operators watch for?
3. TOMORROW SOLAR WINDOW CHARGING DECISION — Should we charge overnight/early morning to be full for tomorrow's solar window? Is DA during HE9-14 high enough to justify it, or is the overnight charging opportunity better used elsewhere?

Be direct and actionable. Use zone names (West, South, North, Houston). Reference specific HEs and dollar amounts. Keep it under 400 words."""

cr = requests.post("https://api.anthropic.com/v1/messages",
    headers={"Content-Type":"application/json","x-api-key":ANTHROPIC_KEY,"anthropic-version":"2023-06-01"},
    json={"model":"claude-sonnet-4-6","max_tokens":600,"system":sys_msg,"messages":[{"role":"user","content":prompt_data}]},
    timeout=60)
analysis = cr.json()["content"][0]["text"]
print("Claude analysis done")

# ─── 7. Build RT HTML ───
Q = chr(39)
rc_map = {"DISPATCH":"#c0392b","HOLD":"#9a6200","MONITOR":"#4BACC6"}

def zone_card(zone):
    d = rt_vs_da[zone]
    rt = d["rt_now"]
    sol = d["da_solar_avg"]
    peak = d["da_peak_price"]
    peak_he = d["da_peak_he"]
    sig = d["signal"]
    col = rc_map.get(sig,"#4BACC6")
    rt_col = "#c0392b" if rt and rt > 50 else "#5db87a" if rt and rt < 10 else "#e8f4f8"
    out = f"<div style={Q}background:#0d1825;border:0.5px solid rgba(75,172,198,0.15);border-radius:10px;padding:1rem{Q}>"
    out += f"<div style={Q}display:flex;justify-content:space-between;align-items:center;margin-bottom:8px{Q}>"
    out += f"<span style={Q}font-size:13px;font-weight:600;color:#e8f4f8{Q}>{zone}</span>"
    out += f"<span style={Q}font-size:10px;font-weight:700;padding:2px 8px;border-radius:3px;background:{col};color:white{Q}>{sig}</span></div>"
    out += f"<div style={Q}display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px{Q}>"
    out += f"<div style={Q}background:#111f30;border-radius:5px;padding:7px{Q}><div style={Q}font-size:9px;color:#3d6478;margin-bottom:2px{Q}>RT NOW</div><div style={Q}font-size:16px;font-weight:600;color:{rt_col};font-family:monospace{Q}>${rt if rt else 'N/A'}</div></div>"
    out += f"<div style={Q}background:#111f30;border-radius:5px;padding:7px{Q}><div style={Q}font-size:9px;color:#3d6478;margin-bottom:2px{Q}>DA SOLAR AVG</div><div style={Q}font-size:16px;font-weight:600;color:#e8f4f8;font-family:monospace{Q}>${sol if sol else 'N/A'}</div></div>"
    out += f"<div style={Q}background:#111f30;border-radius:5px;padding:7px{Q}><div style={Q}font-size:9px;color:#3d6478;margin-bottom:2px{Q}>DA PEAK HE{peak_he}</div><div style={Q}font-size:16px;font-weight:600;color:#c8b87a;font-family:monospace{Q}>${peak if peak else 'N/A'}</div></div>"
    out += "</div></div>"
    return out

def constraint_row(c, i):
    bg = "rgba(224,82,82,0.08)" if c["avg_sp"] > 100 else "rgba(212,135,42,0.07)" if c["avg_sp"] > 30 else "#0d1825"
    col = "#c0392b" if c["avg_sp"] > 100 else "#9a6200" if c["avg_sp"] > 30 else "#4BACC6"
    return (f"<tr style={Q}background:{bg}{Q}>"
        f"<td style={Q}padding:6px 10px;font-size:11px;color:#e8f4f8;border-bottom:1px solid rgba(255,255,255,0.04){Q}>{i}. {c['name']}</td>"
        f"<td style={Q}padding:6px 10px;font-size:12px;font-weight:600;color:{col};border-bottom:1px solid rgba(255,255,255,0.04);font-family:monospace{Q}>${c['avg_sp']}</td>"
        f"<td style={Q}padding:6px 10px;font-size:11px;color:#7ea8bc;border-bottom:1px solid rgba(255,255,255,0.04);font-family:monospace{Q}>${c['max_sp']}</td>"
        f"<td style={Q}padding:6px 10px;font-size:11px;color:#7ea8bc;border-bottom:1px solid rgba(255,255,255,0.04){Q}>{c['hours_binding']}</td>"
        f"<td style={Q}padding:6px 10px;font-size:10px;color:#4BACC6;border-bottom:1px solid rgba(255,255,255,0.04){Q}>{' '.join(['HE'+str(h) for h in c['peak_hours'][:3]])}</td>"
        f"<td style={Q}padding:6px 10px;font-size:10px;color:#7ea8bc;border-bottom:1px solid rgba(255,255,255,0.04){Q}>{c['from_st']} → {c['to_st']}</td>"
        "</tr>")

zone_cards = "".join([zone_card(z) for z in ["WEST","SOUTH","NORTH","HOUSTON"]])
constraint_rows = "".join([constraint_row(c,i+1) for i,c in enumerate(top_constraints)])

# Format analysis text
analysis_html = ""
for para in analysis.strip().split("\n"):
    para = para.strip()
    if not para: continue
    if para.startswith("1.") or para.startswith("2.") or para.startswith("3."):
        analysis_html += f"<div style={Q}font-size:13px;font-weight:600;color:#4BACC6;margin:12px 0 4px{Q}>{para[:2]}</div><div style={Q}font-size:12px;color:#c8d8e8;line-height:1.6;margin-bottom:8px{Q}>{para[2:].strip()}</div>"
    elif para.startswith("**") or para.startswith("#"):
        clean = para.replace("**","").replace("#","").strip()
        analysis_html += f"<div style={Q}font-size:12px;font-weight:600;color:#4BACC6;margin:10px 0 3px{Q}>{clean}</div>"
    else:
        analysis_html += f"<div style={Q}font-size:12px;color:#c8d8e8;line-height:1.6;margin-bottom:6px{Q}>{para}</div>"

html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>HEN RT Analysis {TODAY}</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;background:#070f1a;color:#e8f4f8;min-height:100vh}}</style></head><body>
<div style="background:#022a4e;border-bottom:1px solid rgba(75,172,198,0.25);padding:0 1.5rem;height:52px;display:flex;align-items:center;justify-content:space-between">
<div style="display:flex;align-items:center;gap:10px">
<svg fill="#4BACC6" width="20" height="20" viewBox="0 0 24 24"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
<strong style="font-size:14px">HEN RT Dispatch Analysis</strong></div>
<div style="display:flex;align-items:center;gap:8px">
<a href="results.html" style="font-size:11px;color:#4BACC6;text-decoration:none;background:rgba(75,172,198,0.1);border:1px solid rgba(75,172,198,0.25);padding:3px 10px;border-radius:4px">← Bid Prep</a>
<span style="font-size:11px;color:#4BACC6;background:rgba(75,172,198,0.1);border:1px solid rgba(75,172,198,0.25);padding:3px 10px;border-radius:4px;font-family:monospace">{TODAY} {CDT.strftime('%H:%M CDT')}</span></div></div>
<div style="max-width:960px;margin:0 auto;padding:1.5rem">

<div style="background:#0d1825;border:0.5px solid rgba(75,172,198,0.15);border-radius:10px;padding:1.25rem;margin-bottom:1rem">
<div style="display:flex;align-items:center;gap:10px;margin-bottom:12px">
<div style="width:3px;height:16px;background:#4BACC6;border-radius:2px"></div>
<div style="font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:0.07em;color:#4BACC6">Claude Dispatch Analysis</div>
<span style="font-size:10px;color:#3d6478;font-family:monospace">HE{cur_he} · {CDT.strftime('%H:%M CDT')}</span></div>
{analysis_html}</div>

<div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-bottom:1rem">
{zone_cards}</div>

<div style="background:#0d1825;border:0.5px solid rgba(75,172,198,0.15);border-radius:10px;padding:1.25rem;margin-bottom:1rem">
<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">
<div style="width:3px;height:16px;background:#4BACC6;border-radius:2px"></div>
<div style="font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:0.07em;color:#4BACC6">Yesterday SCED Binding Constraints</div>
<span style="font-size:10px;color:#3d6478">{YESTERDAY} · {len(sced_rows):,} intervals · {len(top_constraints)} constraints</span></div>
<table style="width:100%;border-collapse:collapse">
<thead><tr>
<th style="text-align:left;font-size:9px;color:#3d6478;padding:0 10px 6px;border-bottom:1px solid rgba(255,255,255,0.06)">Constraint</th>
<th style="text-align:left;font-size:9px;color:#3d6478;padding:0 10px 6px;border-bottom:1px solid rgba(255,255,255,0.06)">Avg $/MWh</th>
<th style="text-align:left;font-size:9px;color:#3d6478;padding:0 10px 6px;border-bottom:1px solid rgba(255,255,255,0.06)">Max $/MWh</th>
<th style="text-align:left;font-size:9px;color:#3d6478;padding:0 10px 6px;border-bottom:1px solid rgba(255,255,255,0.06)">Intervals</th>
<th style="text-align:left;font-size:9px;color:#3d6478;padding:0 10px 6px;border-bottom:1px solid rgba(255,255,255,0.06)">Peak HEs</th>
<th style="text-align:left;font-size:9px;color:#3d6478;padding:0 10px 6px;border-bottom:1px solid rgba(255,255,255,0.06)">From → To</th>
</tr></thead>
<tbody>{constraint_rows}</tbody></table></div>

<div style="text-align:center;font-size:10px;color:#3d6478;padding:10px">Data: ERCOT SCED {YESTERDAY} · RT prices {TODAY} HE{cur_he} · DA prices {TOMORROW}</div>
</div></body></html>"""

with open("rt.html","w") as f:
    f.write(html)
print(f"Done. Constraints:{len(top_constraints)} RT_nodes:{len(rt_prices)} DA_nodes:{len(da_prices)}")
