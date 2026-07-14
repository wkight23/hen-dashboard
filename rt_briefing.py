import os, json, requests, re, time
import pandas as pd
from datetime import datetime, date, timedelta, timezone

ERCOT_USER = os.environ["ERCOT_USERNAME"]
ERCOT_PASS = os.environ["ERCOT_PASSWORD"]
ERCOT_SUBKEY = os.environ["ERCOT_SUBKEY"]
ANTHROPIC_KEY = os.environ["ANTHROPIC_API_KEY"]
BASE = "https://api.ercot.com/api/public-reports"
AUTH_URL = "https://ercotb2c.b2clogin.com/ercotb2c.onmicrosoft.com/B2C_1_PUBAPI-ROPC-FLOW/oauth2/v2.0/token"
CDT = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=5)
TODAY = CDT.date().isoformat()
YESTERDAY = (CDT.date() - timedelta(days=1)).isoformat()
TOMORROW = (CDT.date() + timedelta(days=1)).isoformat()
NOW = datetime.now()
SOLAR_HE = set(range(9, 15))

# ─── Site / zone taxonomy (Stage 1 re-zone: West Texas / North Texas / Coastal / Premium) ───
SITE_ZONES = {
    "TOYAH_RN":"WEST_TEXAS","SADLBACK_RN":"WEST_TEXAS","FAULKNER_RN":"WEST_TEXAS","COYOTSPR_RN":"WEST_TEXAS",
    "LONESTAR_RN":"WEST_TEXAS","RTLSNAKE_BT":"WEST_TEXAS","CEDRVALE_RN":"WEST_TEXAS","SBEAN_BESS":"WEST_TEXAS",
    "GOMZ_RN":"WEST_TEXAS","GRDNE_ESR_RN":"WEST_TEXAS","JDKNS_RN":"WEST_TEXAS","SANDLAKE_RN":"WEST_TEXAS",
    "OLNEYTN_RN":"NORTH_TEXAS","DIBOL_RN":"NORTH_TEXAS","FRMRSVLW_RN":"NORTH_TEXAS","MNWL_BESS_RN":"NORTH_TEXAS",
    "LFSTH_RN":"NORTH_TEXAS","PAULN_RN":"NORTH_TEXAS","CISC_RN":"NORTH_TEXAS",
    "MV_VALV4_RN":"COASTAL","WLTC_ESR_RN":"COASTAL","MAINLAND_RN":"COASTAL","FALFUR_RN":"COASTAL",
    "PAVLOV_BT_RN":"COASTAL","POTEETS_RN":"COASTAL","TYNAN_RN":"COASTAL",
    "CATARINA_B1":"PREMIUM","HOLCOMB_RN1":"PREMIUM","HAMI_BESS_RN":"PREMIUM","JUNCTION_RN":"PREMIUM",
    "RUSSEKST_RN":"PREMIUM","FTDUNCAN_RN":"PREMIUM",
}
SITE_NAMES = {"RUSSEKST_RN":"Russek","JUNCTION_RN":"Junction","OLNEYTN_RN":"Olney","GRDNE_ESR_RN":"Garden City","JDKNS_RN":"Judkins","LONESTAR_RN":"Lonestar","RTLSNAKE_BT":"Rattlesnake","SANDLAKE_RN":"Sandlake","CEDRVALE_RN":"Cedarvale","COYOTSPR_RN":"Coyote","FAULKNER_RN":"Faulkner","SADLBACK_RN":"Saddleback","TOYAH_RN":"Toyah","GOMZ_RN":"Gomez","SBEAN_BESS":"Screwbean","HAMI_BESS_RN":"Hamilton","FTDUNCAN_RN":"Fort Duncan","CATARINA_B1":"Catarina","HOLCOMB_RN1":"Holcomb","POTEETS_RN":"Poteets","FALFUR_RN":"Falfurrias","MV_VALV4_RN":"Val Verde","TYNAN_RN":"Tynan","WLTC_ESR_RN":"Weil Tract","PAVLOV_BT_RN":"Pavlov","MAINLAND_RN":"Mainland","DIBOL_RN":"Diboll","PAULN_RN":"Pauline","FRMRSVLW_RN":"Farmersville","MNWL_BESS_RN":"Mineral Wells","CISC_RN":"Cisco","LFSTH_RN":"Lufkin South"}
ZONE_LABELS = {"WEST_TEXAS":"West Texas","NORTH_TEXAS":"North Texas","COASTAL":"Coastal","PREMIUM":"Premium"}
ZONE_HUBS = {"WEST_TEXAS":"LZ_WEST","NORTH_TEXAS":"LZ_NORTH","COASTAL":"LZ_SOUTH"}
COASTAL_SECONDARY_HUB = "LZ_HOUSTON"   # Mainland physically prices off Houston, not South
PREMIUM_NODES = ["CATARINA_B1","HOLCOMB_RN1","HAMI_BESS_RN","JUNCTION_RN","RUSSEKST_RN","FTDUNCAN_RN"]
PREMIUM_HOME_HUB = {"CATARINA_B1":"LZ_SOUTH","HOLCOMB_RN1":"LZ_SOUTH","HAMI_BESS_RN":"LZ_SOUTH","FTDUNCAN_RN":"LZ_SOUTH","JUNCTION_RN":"LZ_WEST","RUSSEKST_RN":"LZ_WEST"}
SF_TO_SP = {'Russek':'RUSSEKST_RN','Catarina':'CATARINA_B1','Holcomb':'HOLCOMB_RN1','Hamilton':'HAMI_BESS_RN','FortDuncan':'FTDUNCAN_RN','Junction':'JUNCTION_RN','Judkins':'JDKNS_RN','Saddleback':'SADLBACK_RN','Cedarvale':'CEDRVALE_RN','Toyah':'TOYAH_RN','Coyote':'COYOTSPR_RN','Faulkner':'FAULKNER_RN','GardenCity':'GRDNE_ESR_RN','Gomez':'GOMZ_RN','Lonestar':'LONESTAR_RN','Rattlesnake':'RTLSNAKE_BT','Sandlake':'SANDLAKE_RN','Screwbean':'SBEAN_BESS','ValVerde':'MV_VALV4_RN','Falfurrias':'FALFUR_RN','Pavlov':'PAVLOV_BT_RN','Poteets':'POTEETS_RN','Tynan':'TYNAN_RN','WeilTract':'WLTC_ESR_RN','Mainland':'MAINLAND_RN','Cisco':'CISC_RN','Diboll':'DIBOL_RN','Farmersville':'FRMRSVLW_RN','LufkinSouth':'LFSTH_RN','MineralWells':'MNWL_BESS_RN','Olney':'OLNEYTN_RN','Pauline':'PAULN_RN'}
# Heuristic fallback only used when a constraint name isn't found in the shift factor workbook below.
HEN_TOKENS = {k.upper(): k for k in SF_TO_SP.keys()}

def load_shift_factor_data(path="Congestion_Proj_heatmap.xlsx"):
    """Read the live shift-factor / historical-shadow-pricing workbook from the repo.
    Returns {} if the file isn't there yet so the rest of the script still runs."""
    sf_data = {}
    try:
        df = pd.read_excel(path, header=None)
        site_order = list(SF_TO_SP.keys())  # matches the workbook's column order (cols 30-61)
        for i in range(1, len(df)):
            name = df.iat[i, 0]
            if pd.isna(name) or str(name).strip().lower() == "new lines":
                continue
            name = str(name).strip()
            try:
                total = float(df.iat[i, 2])
            except: total = 0.0
            hourly = []
            for h in range(24):
                try: hourly.append(float(df.iat[i, 3+h]))
                except: hourly.append(0.0)
            sf = {}
            for j, site in enumerate(site_order):
                try:
                    val = float(df.iat[i, 30+j])
                    if val: sf[site] = val
                except: continue
            peak_he = [h+1 for h,_ in sorted(enumerate(hourly), key=lambda x:-x[1])[:3]]
            sf_data[name] = {"sf": sf, "total": total, "hourly": hourly, "peak_he": peak_he}
        print(f"Loaded shift factor data: {len(sf_data)} constraints from {path}")
    except FileNotFoundError:
        print(f"No shift factor workbook found at {path} - skipping (heuristic HEN matching will be used instead)")
    except Exception as e:
        print(f"Could not load shift factor workbook: {e}")
    return sf_data

SF_DATA = load_shift_factor_data()

def load_playbook(path="HEN_NOC_Congestion_Playbook.xlsx"):
    """Load the HEN NOC Congestion Playbook Line Lookup tab into a searchable dict.
    Keys are normalized uppercase tokens from the line name for fuzzy matching."""
    playbook = {}
    try:
        df = pd.read_excel(path, sheet_name="📋 Line Lookup", header=2)
        SKIP = {"line / constraint","legend:","🟢  active","🟡  watch","⚫  low priority"}
        for _, row in df.iterrows():
            name = str(row.get("Line / Constraint","")).strip()
            if not name or name.lower()[:20] in SKIP or any(s in name.lower() for s in ["active —","watch —","low priority —","legend:"]): continue
            priority = str(row.get("Priority","")).strip()
            if not priority or priority == "nan": continue
            driver = str(row.get("Gen Level Trigger\n(What Drives It)","")).strip()
            if driver == "nan": driver = ""
            strategy = str(row.get("Hold Strategy /\nDischarge Timing","")).strip()
            if strategy == "nan": strategy = ""
            notes = str(row.get("Operator Notes","")).strip()
            if notes == "nan": notes = ""
            other = str(row.get("Other Active\nNodes (SF)","")).strip()
            if other == "nan": other = ""
            peak_he = str(row.get("Peak HE\n(Active Hrs)","")).strip()
            if peak_he == "nan": peak_he = ""
            entry = {
                "line": name,
                "priority": priority,
                "season": str(row.get("Season","")).replace("nan","").strip(),
                "peak_he": peak_he,
                "driver": driver,
                "primary_node": str(row.get("Primary Node","")).replace("nan","—").strip(),
                "sf": row.get("Shift\nFactor"),
                "mcc_500": row.get("MCC @\n$500 SP"),
                "mcc_1000": row.get("MCC @\n$1,000 SP"),
                "mcc_2000": row.get("MCC @\n$2,000 SP"),
                "other_nodes": other,
                "strategy": strategy,
                "notes": notes,
            }
            # Store under normalized tokens for fuzzy matching
            tokens = name.upper().replace(" ","").replace("-","").replace("_","").replace("138KV","").replace("345KV","").replace("69KV","").replace("115KV","").replace("1KV","")
            playbook[name.upper()] = entry   # exact key (uppercase)
            playbook[tokens] = entry          # tokenized key
        print(f"Playbook loaded: {len([e for e in playbook.values() if '🟢' in e['priority']])} Active, "
              f"{len([e for e in playbook.values() if '🟡' in e['priority']])} Watch lines")
    except FileNotFoundError:
        print("Playbook not found — skipping (upload HEN_NOC_Congestion_Playbook.xlsx to repo root)")
    except Exception as e:
        print(f"Playbook load error: {e}")
    return playbook

PLAYBOOK = load_playbook()

def hen_match_sf(name):
    """Real HEN-relevance check using the shift factor workbook, keyed by exact constraint name."""
    entry = SF_DATA.get(name)
    if not entry: return None
    hits = []
    for site_key, val in entry["sf"].items():
        if abs(val) >= 0.05:
            site_code = SF_TO_SP.get(site_key)
            hits.append(SITE_NAMES.get(site_code, site_key))
    return hits

def match_playbook(constraint_name, from_st, to_st):
    """Match a SCED constraint to its playbook entry using exact then fuzzy station matching."""
    if not PLAYBOOK: return None
    # 1. Direct constraint name match
    cn = constraint_name.upper()
    if cn in PLAYBOOK: return PLAYBOOK[cn]
    # 2. Tokenized constraint name match
    tok = cn.replace(" ","").replace("-","").replace("_","")
    if tok in PLAYBOOK: return PLAYBOOK[tok]
    # 3. Station name matching — find entries where both from/to appear in the line name
    f = str(from_st).upper()[:6]
    t = str(to_st).upper()[:6]
    for key, entry in PLAYBOOK.items():
        lname = entry["line"].upper()
        if len(f) >= 4 and len(t) >= 4 and f[:4] in lname and t[:4] in lname:
            return entry
    return None


    """Real HEN-relevance check using the shift factor workbook, keyed by exact constraint name."""
    entry = SF_DATA.get(name)
    if not entry: return None
    hits = []
    for site_key, val in entry["sf"].items():
        if abs(val) >= 0.05:
            site_code = SF_TO_SP.get(site_key)
            hits.append(SITE_NAMES.get(site_code, site_key))
    return hits

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

def hen_match(from_st, to_st):
    """Best-effort: does this constraint's from/to station mention a HEN node? Heuristic only."""
    blob = (str(from_st) + " " + str(to_st)).upper().replace(" ","").replace("-","")
    hits = [name for token, name in HEN_TOKENS.items() if token in blob]
    return hits

def fetch_sced_constraints(ts_from, ts_to, label):
    """Pull SCED binding shadow prices for a window and roll up into a constraint summary list."""
    print(f"Fetching SCED constraints ({label})...")
    rows = []
    for page in range(1, 5):
        try:
            r = requests.get(BASE+"/np6-86-cd/shdw_prices_bnd_trns_const",
                params={"SCEDTimestampFrom":ts_from,"SCEDTimestampTo":ts_to,"page":page,"size":5000},
                headers=hdrs, timeout=30)
            if r.ok:
                d = r.json()
                page_rows = d.get("data",[])
                rows.extend(page_rows)
                if len(page_rows) < 5000: break
            else:
                break
        except: break
    print(f"SCED rows ({label}): {len(rows)}")

    constraints = {}
    for row in rows:
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

    out = []
    for name, data in constraints.items():
        sps = data["shadow_prices"]
        avg_sp = sum(sps)/len(sps)
        max_sp = max(sps)
        min_sp = min(sps)
        hours = sorted(data["hours"])
        sf_hits = hen_match_sf(name)
        hits = sf_hits if sf_hits is not None else hen_match(data["from_st"], data["to_st"])
        sf_entry = SF_DATA.get(name)
        pb = match_playbook(name, data["from_st"], data["to_st"])
        out.append({
            "name": name,
            "avg_sp": round(avg_sp, 2),
            "max_sp": round(max_sp, 2),
            "min_sp": round(min_sp, 2),
            "hours_binding": len(sps),
            "peak_hours": hours[:5],
            "from_st": data["from_st"],
            "to_st": data["to_st"],
            "hen_sites": hits,
            "hist_total": sf_entry["total"] if sf_entry else None,
            "hist_peak_he": sf_entry["peak_he"] if sf_entry else None,
            "playbook": pb,
        })
    # HEN-relevant constraints bubble to the top, then by impact (avg_sp x hours_binding)
    out.sort(key=lambda x: (0 if x["hen_sites"] else 1, -(x["avg_sp"] * x["hours_binding"])))
    return rows, out

# ─── 1. SCED Shadow Prices: yesterday (full day) + today (live, partial) ───
sced_rows_y, constraint_list_y = fetch_sced_constraints(YESTERDAY+"T00:00:00", YESTERDAY+"T23:59:59", "yesterday")
top_constraints = constraint_list_y[:15]

ts_to_today = CDT.strftime("%Y-%m-%dT%H:%M:%S")
sced_rows_t, constraint_list_t = fetch_sced_constraints(TODAY+"T00:00:00", ts_to_today, "today, live")
top_today_constraints = constraint_list_t[:10]

# Flag stacked congestion: a HEN node showing up in 2+ of today's binding constraints
site_hit_counts = {}
for c in top_today_constraints:
    for site in c["hen_sites"]:
        site_hit_counts[site] = site_hit_counts.get(site, 0) + 1
stacked_sites = [s for s, n in site_hit_counts.items() if n >= 2]

# ─── 2. RT prices: 5-minute SCED LMPs (catches single-interval spikes, not a 15-min average) ───
print("Fetching RT prices...")
rt_prices = {}
KEY_NODES = ["LZ_WEST","LZ_NORTH","LZ_SOUTH","LZ_HOUSTON"] + PREMIUM_NODES
for node in KEY_NODES:
    try:
        r = requests.get(BASE+"/np6-788-cd/lmp_node_zone_hub",
            params={"settlementPoint":node,"SCEDTimestampFrom":TODAY+"T00:00:00","SCEDTimestampTo":ts_to_today,"size":500},
            headers=hdrs, timeout=15)
        if r.ok:
            d = r.json()
            fields = d.get("fields",[])
            rows = d.get("data",[])
            ts_col = next((f["cardinality"]-1 for f in fields if "sced" in f.get("name","").lower() or "timestamp" in f.get("name","").lower()), 0)
            pr_col = next((f["cardinality"]-1 for f in fields if "lmp" in f.get("name","").lower() or "price" in f.get("name","").lower()), 1)
            valid_rows = [r_ for r_ in rows if isinstance(r_, list) and len(r_) > max(ts_col, pr_col)]
            if valid_rows:
                latest = max(valid_rows, key=lambda r_: str(r_[ts_col]))
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
def zone_metrics(rt_price, da_hub):
    solar_da_avg = None
    if da_hub:
        solar_prices = [da_hub[he] for he in SOLAR_HE if he in da_hub]
        if solar_prices: solar_da_avg = round(sum(solar_prices)/len(solar_prices), 2)
    peak_he = max(da_hub, key=da_hub.get) if da_hub else None
    peak_price = da_hub.get(peak_he) if peak_he else None
    signal = "HOLD" if (rt_price and peak_price and peak_price > rt_price * 1.2) else "DISPATCH" if (rt_price and rt_price > 50) else "MONITOR"
    return {"rt_now": rt_price, "da_solar_avg": solar_da_avg, "da_peak_he": peak_he, "da_peak_price": peak_price, "signal": signal}

rt_vs_da = {}
for zone, hub in ZONE_HUBS.items():
    rt_vs_da[zone] = zone_metrics(rt_prices.get(hub), da_prices.get(hub, {}))
# Coastal's secondary node (Mainland) prices off Houston, not South - tracked alongside the Coastal card
coastal_secondary = zone_metrics(rt_prices.get(COASTAL_SECONDARY_HUB), da_prices.get(COASTAL_SECONDARY_HUB, {}))

premium_metrics = {}
for node in PREMIUM_NODES:
    home_hub = PREMIUM_HOME_HUB[node]
    premium_metrics[node] = zone_metrics(rt_prices.get(node), da_prices.get(home_hub, {}))

# ─── 5. Verdict: pick the single most actionable signal across zones + premium nodes ───
candidates = []
for zone, m in rt_vs_da.items():
    candidates.append({"label": ZONE_LABELS[zone], "scope":"zone", **m})
for node, m in premium_metrics.items():
    candidates.append({"label": SITE_NAMES.get(node, node), "scope":"premium", **m})

dispatch_candidates = [c for c in candidates if c["signal"] == "DISPATCH" and c["rt_now"]]
charge_candidates = [c for c in candidates if c["rt_now"] is not None and c["rt_now"] < 5]
if dispatch_candidates:
    verdict = max(dispatch_candidates, key=lambda c: c["rt_now"])
    verdict["action"] = "DISPATCH"
elif charge_candidates:
    verdict = min(charge_candidates, key=lambda c: c["rt_now"])
    verdict["action"] = "CHARGE"
else:
    verdict = max(candidates, key=lambda c: c["rt_now"] or -999)
    verdict["action"] = "MONITOR"

# ─── 6. Build prompt for Claude ───
print("Calling Claude for RT analysis...")
cur_he = CDT.hour + 1

prompt_data = f"HEN RT Dispatch Analysis - {TODAY} {CDT.strftime('%H:%M CDT')}\n"
prompt_data += f"Current HE: {cur_he}\n\n"

prompt_data += "=== CURRENT RT LMPs (zone hubs) ===\n"
for zone, hub in ZONE_HUBS.items():
    rt = rt_prices.get(hub, "N/A")
    prompt_data += f"{ZONE_LABELS[zone]} ({hub}): ${rt}/MWh\n"
prompt_data += f"Mainland (Coastal, prices off LZ_HOUSTON): ${rt_prices.get(COASTAL_SECONDARY_HUB,'N/A')}/MWh\n"

prompt_data += "\n=== PREMIUM NODES (individually tracked, RT-volatile) ===\n"
for node in PREMIUM_NODES:
    rt = rt_prices.get(node, "N/A")
    prompt_data += f"{SITE_NAMES.get(node,node)} ({node}): ${rt}/MWh\n"

prompt_data += "\n=== TOMORROW DA PRICES - SOLAR WINDOW (HE9-14) ===\n"
for zone, hub in ZONE_HUBS.items():
    da_hub = da_prices.get(hub, {})
    solar = {he: da_hub[he] for he in SOLAR_HE if he in da_hub}
    if solar:
        avg = round(sum(solar.values())/len(solar), 2)
        peak_he = max(solar, key=solar.get)
        prompt_data += f"{ZONE_LABELS[zone]}: Solar avg ${avg}/MWh, peak HE{peak_he} ${solar[peak_he]}/MWh\n"
    else:
        prompt_data += f"{ZONE_LABELS[zone]}: No DA data\n"

prompt_data += "\n=== TOMORROW DA PRICES - FULL DAY ===\n"
for zone, hub in ZONE_HUBS.items():
    da_hub = da_prices.get(hub, {})
    if da_hub:
        sorted_he = sorted(da_hub.items())
        prices_str = " ".join([f"HE{he}:${p}" for he,p in sorted_he])
        prompt_data += f"{ZONE_LABELS[zone]}: {prices_str}\n"

prompt_data += "\n=== TODAY'S LIVE SCED BINDING CONSTRAINTS (so far, top 10, HEN-relevant flagged) ===\n"
for c in top_today_constraints:
    flag = f" [HEN: {', '.join(c['hen_sites'])}]" if c["hen_sites"] else ""
    hist = f" | historically totals ${c['hist_total']:,.0f} since the workbook's date range, typically peaking HE{c['hist_peak_he']}" if c.get("hist_total") else ""
    prompt_data += f"{c['from_st']} -> {c['to_st']} ({c['name']}): avg ${c['avg_sp']} min ${c['min_sp']} max ${c['max_sp']}/MWh, {c['hours_binding']} intervals, peak HEs {c['peak_hours'][:3]}{flag}{hist}\n"
if stacked_sites:
    prompt_data += f"STACKED CONGESTION WARNING: {', '.join(stacked_sites)} each appear in 2+ binding constraints today.\n"

prompt_data += "\n=== YESTERDAY SCED BINDING CONSTRAINTS (Top 10 by impact, full day) ===\n"
for c in top_constraints[:10]:
    flag = f" [HEN: {', '.join(c['hen_sites'])}]" if c["hen_sites"] else ""
    hist = f" | historically totals ${c['hist_total']:,.0f}, typically peaking HE{c['hist_peak_he']}" if c.get("hist_total") else ""
    prompt_data += f"{c['from_st']} -> {c['to_st']} ({c['name']}): avg ${c['avg_sp']} min ${c['min_sp']} max ${c['max_sp']}/MWh, {c['hours_binding']} intervals, peak HEs {c['peak_hours'][:3]}{flag}{hist}\n"

# ─── Playbook context for all binding constraints (today + yesterday) ───
all_seen = {c["name"]: c for c in top_today_constraints + top_constraints}
playbook_context = []
for cname, c in all_seen.items():
    pb = c.get("playbook")
    if pb and pb.get("driver"):
        playbook_context.append(
            f"  {pb['line']} [{pb['priority'].replace('🟢','Active').replace('🟡','Watch').replace('⚫','Low')}]:\n"
            f"    Driver: {pb['driver']}\n"
            f"    Season: {pb['season']} | Historical peak HEs: {pb['peak_he']}\n"
            f"    Primary node: {pb['primary_node']} | MCC@$1k: ${pb['mcc_1000']}\n"
            + (f"    Strategy: {pb['strategy']}\n" if pb.get("strategy") else "")
            + (f"    Notes: {pb['notes']}\n" if pb.get("notes") else "")
        )
if playbook_context:
    prompt_data += "\n=== NOC PLAYBOOK — KNOWN DRIVERS FOR BINDING CONSTRAINTS ===\n"
    prompt_data += "\n".join(playbook_context)
    prompt_data += "\nUse this to assess: (a) do current conditions match the known driver? (b) does the forecast suggest this constraint will repeat tonight?\n"


prompt_data += "\n=== RT vs DA ZONE SIGNALS ===\n"
for zone, m in rt_vs_da.items():
    prompt_data += f"{ZONE_LABELS[zone]}: RT now ${m['rt_now']}/MWh | DA solar avg ${m['da_solar_avg']}/MWh | DA peak HE{m['da_peak_he']} ${m['da_peak_price']}/MWh | Signal: {m['signal']}\n"
prompt_data += "\n=== RT vs DA PREMIUM NODE SIGNALS ===\n"
for node, m in premium_metrics.items():
    prompt_data += f"{SITE_NAMES.get(node,node)}: RT now ${m['rt_now']}/MWh | DA solar avg ${m['da_solar_avg']}/MWh | DA peak HE{m['da_peak_he']} ${m['da_peak_price']}/MWh | Signal: {m['signal']}\n"

sys_msg = """You are a real-time dispatch analyst for Hunt Energy Network (HEN), a 32-site battery storage operator in ERCOT, organized into West Texas, North Texas, Coastal, and a Premium tier of six RT-volatile sites watched more closely (Catarina, Holcomb, Hamilton, Junction, Russek, Fort Duncan).

CRITICAL FRAMING RULES:
- Negative DART (DA < RT) means RT exceeded DA — FAVORABLE for RT-dispatched batteries, not underperformance
- Positive SF x positive shadow price = congestion BENEFIT at that node (LMP pushed higher, good for discharge)
- Negative SF x positive shadow price = congestion COST at that node (LMP pushed lower, charging opportunity)
- WESTEX constraint: West Texas sites (Judkins/Saddleback/Cedarvale/etc) have SF ~ -0.71, so when WESTEX binds, those sites see near-zero or negative LMP — CHARGE don't dispatch
- MCC threshold: >$10/MWh on a HEN node is commercially significant
- Premium nodes are individually tracked because they run more RT-volatile than their zone average — call out divergence between a Premium node and its home zone explicitly when it matters
- If a HEN node shows up in 2+ binding constraints today (stacked congestion), call this out specifically — it's a bigger commercial risk/opportunity than any single constraint

Answer four questions clearly:
1. WHAT IS HAPPENING RIGHT NOW — Are current RT prices favorable for dispatch? Which zones or premium nodes specifically?
2. WHAT TO EXPECT LATER TODAY/TONIGHT — Based on today's live constraint pattern, yesterday's full-day pattern, and current RT, what should operators watch for?
3. TOMORROW SOLAR WINDOW CHARGING DECISION — Should we charge overnight/early morning to be full for tomorrow's solar window? Is DA during HE9-14 high enough to justify it, or is the overnight charging opportunity better used elsewhere?
4. YESTERDAY & TODAY CONGESTION DEBRIEF — A short, plain-language recap of what the binding constraints actually did. For each constraint that has a playbook entry, explicitly state whether the observed conditions (wind/load levels) appear consistent with the known driver, or whether the constraint behaved unexpectedly. Call out stacked congestion on a single HEN node. Flag any constraint with no playbook match as a potential new topology event worth tracking. Keep it tight — one sentence per notable constraint, skip anything not commercially relevant to HEN.

Be direct and actionable. Use zone names (West Texas, North Texas, Coastal) and premium node names when relevant. Reference specific HEs and dollar amounts. Keep each section tight - the whole response under 500 words."""

cr = requests.post("https://api.anthropic.com/v1/messages",
    headers={"Content-Type":"application/json","x-api-key":ANTHROPIC_KEY,"anthropic-version":"2023-06-01"},
    json={"model":"claude-sonnet-4-6","max_tokens":600,"system":sys_msg,"messages":[{"role":"user","content":prompt_data}]},
    timeout=60)
analysis = cr.json()["content"][0]["text"]
print("Claude analysis done")

# ─── 7. Build RT HTML ───
Q = chr(39)
rc_map = {"DISPATCH":"#e0584f","HOLD":"#d6a83f","MONITOR":"#4BACC6","CHARGE":"#4fcf8a"}

def zone_card(label, m, highlight=False):
    rt = m["rt_now"]
    sol = m["da_solar_avg"]
    peak = m["da_peak_price"]
    peak_he = m["da_peak_he"]
    sig = m["signal"]
    col = rc_map.get(sig,"#4BACC6")
    rt_col = "#e0584f" if rt and rt > 50 else "#4fcf8a" if rt is not None and rt < 10 else "#eef4f8"
    border = "border-color:rgba(224,88,79,0.4)" if highlight else ""
    out = f"<div class={Q}card{Q} style={Q}padding:0.9rem;{border}{Q}>"
    out += f"<div style={Q}display:flex;justify-content:space-between;align-items:center;margin-bottom:10px{Q}>"
    out += f"<span style={Q}font-size:12px;font-weight:600{Q}>{label}</span>"
    out += f"<span style={Q}font-size:9px;font-weight:600;padding:2px 7px;border-radius:3px;background:{col}22;color:{col}{Q}>{sig.lower()}</span></div>"
    out += f"<div class={Q}mono{Q} style={Q}font-size:18px;font-weight:600;color:{rt_col};margin-bottom:8px{Q}>${rt if rt is not None else 'N/A'}</div>"
    out += f"<div style={Q}display:flex;justify-content:space-between{Q}><span class={Q}lbl{Q}>DA solar avg</span><span class={Q}mono{Q} style={Q}color:#7ea8bc;font-size:10px{Q}>${sol if sol is not None else 'N/A'}</span></div>"
    out += f"<div style={Q}display:flex;justify-content:space-between;margin-top:3px{Q}><span class={Q}lbl{Q}>DA peak HE{peak_he if peak_he else ''}</span><span class={Q}mono{Q} style={Q}color:#c8b87a;font-size:10px{Q}>${peak if peak is not None else 'N/A'}</span></div>"
    out += "</div>"
    return out

def constraint_row(c, i, prefix="r"):
    bg = "rgba(224,88,79,0.08)" if c["avg_sp"] > 100 else "rgba(214,168,63,0.07)" if c["avg_sp"] > 30 else ""
    col = "#e0584f" if c["avg_sp"] > 100 else "#d6a83f" if c["avg_sp"] > 30 else "#4BACC6"
    hen_badge = f"<span style={Q}font-size:9px;font-weight:600;color:#4fcf8a;margin-left:6px{Q}>{'/'.join(c['hen_sites'][:2])}</span>" if c.get("hen_sites") else ""
    pb = c.get("playbook")

    # Build the first-cell content: line name + HEN badge + playbook info always visible
    driver_line = ""
    meta_line = ""
    strategy_line = ""
    if pb and pb.get("driver"):
        pri_col = "#4fcf8a" if "🟢" in pb["priority"] else "#d6a83f" if "🟡" in pb["priority"] else "#5c7a8c"
        pri_label = "Active" if "🟢" in pb["priority"] else "Watch" if "🟡" in pb["priority"] else "Low"
        driver_short = pb["driver"][:120] + ("…" if len(pb["driver"]) > 120 else "")
        season = pb.get("season","")
        peak_he = pb.get("peak_he","")
        strategy = pb.get("strategy","")
        driver_line = (f"<div style={Q}font-size:10px;color:#7ea8bc;margin-top:3px;line-height:1.4{Q}>"
                       f"<span style={Q}font-size:9px;font-weight:600;padding:1px 5px;border-radius:2px;"
                       f"background:{pri_col}22;color:{pri_col};margin-right:5px{Q}>{pri_label}</span>"
                       f"{driver_short}</div>")
        parts = []
        if season: parts.append(season)
        if peak_he: parts.append(f"Peak: {peak_he}")
        if pb.get("primary_node","—") != "—": parts.append(pb["primary_node"])
        if parts:
            meta_line = (f"<div style={Q}font-size:9px;color:#3d5a70;margin-top:2px{Q}>"
                         + " &nbsp;·&nbsp; ".join(parts) + "</div>")
        if strategy:
            strategy_line = (f"<div style={Q}font-size:9px;color:#d6a83f;margin-top:2px;"
                             f"font-style:italic{Q}>{strategy}</div>")

    main_row = (f"<tr style={Q}background:{bg}{Q}>"
        f"<td style={Q}padding:6px 10px;border-bottom:0.5px solid rgba(255,255,255,0.04){Q}>"
        f"<div style={Q}font-size:12px;font-weight:600;color:#eef4f8{Q}>{i}. {c['from_st']} → {c['to_st']}{hen_badge}</div>"
        f"{driver_line}{meta_line}{strategy_line}"
        f"</td>"
        f"<td class={Q}mono{Q} style={Q}padding:6px 10px;font-size:10px;color:#5c7a8c;border-bottom:0.5px solid rgba(255,255,255,0.04){Q}>{c['name']}</td>"
        f"<td class={Q}mono{Q} style={Q}padding:6px 10px;font-size:12px;font-weight:600;color:{col};border-bottom:0.5px solid rgba(255,255,255,0.04){Q}>${c['avg_sp']}</td>"
        f"<td class={Q}mono{Q} style={Q}padding:6px 10px;font-size:11px;color:#7ea8bc;border-bottom:0.5px solid rgba(255,255,255,0.04){Q}>${c['max_sp']}</td>"
        f"<td class={Q}mono{Q} style={Q}padding:6px 10px;font-size:11px;color:#7ea8bc;border-bottom:0.5px solid rgba(255,255,255,0.04){Q}>${c['min_sp']}</td>"
        f"<td class={Q}mono{Q} style={Q}padding:6px 10px;font-size:11px;color:#7ea8bc;border-bottom:0.5px solid rgba(255,255,255,0.04){Q}>{c['hours_binding']}</td>"
        f"<td class={Q}mono{Q} style={Q}padding:6px 10px;font-size:10px;color:#4BACC6;border-bottom:0.5px solid rgba(255,255,255,0.04){Q}>{' '.join(['HE'+str(h) for h in c['peak_hours'][:3]])}</td>"
        "</tr>")
    return main_row

def constraint_table(rows, header_color="#4BACC6"):
    return (f"<table style={Q}width:100%;border-collapse:collapse{Q}><thead><tr>"
        f"<th style={Q}text-align:left;font-size:9px;color:#3d5a70;padding:0 10px 6px;border-bottom:0.5px solid rgba(255,255,255,0.06){Q}>From → to</th>"
        f"<th style={Q}text-align:left;font-size:9px;color:#3d5a70;padding:0 10px 6px;border-bottom:0.5px solid rgba(255,255,255,0.06){Q}>Constraint</th>"
        f"<th style={Q}text-align:left;font-size:9px;color:#3d5a70;padding:0 10px 6px;border-bottom:0.5px solid rgba(255,255,255,0.06){Q}>Avg $/MWh</th>"
        f"<th style={Q}text-align:left;font-size:9px;color:#3d5a70;padding:0 10px 6px;border-bottom:0.5px solid rgba(255,255,255,0.06){Q}>Max $/MWh</th>"
        f"<th style={Q}text-align:left;font-size:9px;color:#3d5a70;padding:0 10px 6px;border-bottom:0.5px solid rgba(255,255,255,0.06){Q}>Min $/MWh</th>"
        f"<th style={Q}text-align:left;font-size:9px;color:#3d5a70;padding:0 10px 6px;border-bottom:0.5px solid rgba(255,255,255,0.06){Q}>Intervals</th>"
        f"<th style={Q}text-align:left;font-size:9px;color:#3d5a70;padding:0 10px 6px;border-bottom:0.5px solid rgba(255,255,255,0.06){Q}>Peak HEs</th>"
        f"</tr></thead><tbody>{rows}</tbody></table>")

geo_cards = "".join([zone_card(ZONE_LABELS[z], rt_vs_da[z]) for z in ["WEST_TEXAS","NORTH_TEXAS","COASTAL"]])
geo_cards += zone_card("Mainland (Houston zone)", coastal_secondary)
premium_cards = "".join([zone_card(SITE_NAMES.get(n,n), premium_metrics[n], highlight=True) for n in PREMIUM_NODES])
today_rows = "".join([constraint_row(c,i+1,"t") for i,c in enumerate(top_today_constraints)])
yesterday_rows = "".join([constraint_row(c,i+1,"y") for i,c in enumerate(top_constraints)])

stacked_html = ""
if stacked_sites:
    stacked_html = f"<div style={Q}font-size:11px;color:#e0584f;margin-bottom:10px{Q}>⚠ Stacked congestion: {', '.join(stacked_sites)} {'each appear' if len(stacked_sites)>1 else 'appears'} in 2+ binding constraints today.</div>"

# Format Claude analysis text - sections 1-3 go to Outlook, section 4 (debrief) goes to Historical
outlook_html = ""
debrief_html = ""
current_section = 1
for para in analysis.strip().split("\n"):
    para = para.strip()
    if not para: continue
    if para.startswith("1.") or para.startswith("2.") or para.startswith("3.") or para.startswith("4."):
        current_section = int(para[0])
        block = f"<div style={Q}font-size:12px;font-weight:600;color:#4BACC6;margin:12px 0 4px{Q}>{para[:2]}</div><div style={Q}font-size:13px;color:#c8d8e8;line-height:1.65;margin-bottom:8px{Q}>{para[2:].strip()}</div>"
    elif para.startswith("**") or para.startswith("#"):
        clean = para.replace("**","").replace("#","").strip()
        block = f"<div style={Q}font-size:12px;font-weight:600;color:#4BACC6;margin:10px 0 3px{Q}>{clean}</div>"
    else:
        block = f"<div style={Q}font-size:13px;color:#c8d8e8;line-height:1.65;margin-bottom:6px{Q}>{para}</div>"
    if current_section == 4:
        debrief_html += block
    else:
        outlook_html += block

verdict_label = verdict["label"]
verdict_action = verdict["action"]
verdict_rt = verdict["rt_now"]
verdict_col = rc_map.get(verdict_action, "#4BACC6")
verdict_border_rgba = {"DISPATCH":"224,88,79","CHARGE":"79,207,138","MONITOR":"75,172,198"}.get(verdict_action, "75,172,198")
verdict_sub = {
    "DISPATCH": f"Best RT value across zones and premium nodes right now",
    "CHARGE": f"Negative/near-zero LMP — charging window, not a discharge one",
    "MONITOR": f"No clear edge yet — nothing crosses the dispatch or charge threshold",
}.get(verdict_action, "")

run_control_html = f"""<div class="card" style="padding:1rem 1.25rem;margin-bottom:1.25rem">
<div style="display:flex;align-items:center;justify-content:space-between;gap:1rem;flex-wrap:wrap">
<div>
<div class="eyebrow" style="margin-bottom:4px">Run analysis</div>
<div style="font-size:11px;color:#7ea8bc">Anyone on the team can trigger a fresh pull. Your GitHub token stays in your browser only.</div>
</div>
<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
<input type="password" id="gh-token" placeholder="ghp_xxxxxxxxxxxxxxxxxxxx" style="width:200px" />
<button class="btn" onclick="saveToken()" style="background:#111f30;border:0.5px solid rgba(75,172,198,0.3);color:#4BACC6;padding:8px 14px;font-size:12px">Save</button>
<button class="btn" id="run-btn" onclick="runAnalysis()" style="background:#e0584f;color:white;padding:8px 18px;font-size:12px;white-space:nowrap">⚡ Run analysis</button>
</div>
</div>
<div id="token-status" style="font-size:11px;color:#3d5a70;margin-top:8px"></div>
<div id="status-msg" style="font-size:11px;color:#7ea8bc;margin-top:4px;min-height:16px"></div>
<div id="progress-bar" style="display:none;margin-top:8px">
<div style="background:#111f30;border-radius:4px;height:3px;overflow:hidden"><div id="progress-fill" style="background:#4BACC6;height:100%;width:0%;transition:width 1s linear"></div></div>
</div>
</div>"""

html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>HEN RT Analysis {TODAY}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<script src="chart.umd.min.js" onload="if(window._chartPending)loadOutlookChart()"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Inter',-apple-system,sans-serif;background:#05080d;color:#eef4f8;min-height:100vh}}
.mono{{font-family:'JetBrains Mono',monospace}}
.btn{{cursor:pointer;border:none;border-radius:6px;font-weight:600;transition:opacity 0.2s}}
.btn:hover{{opacity:0.85}}
.btn:disabled{{opacity:0.4;cursor:not-allowed}}
input{{background:#111f30;border:1px solid rgba(75,172,198,0.3);border-radius:6px;color:#eef4f8;padding:8px 12px;font-size:13px}}
input:focus{{outline:none;border-color:#4BACC6}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:0.25}}}}
.livedot{{width:6px;height:6px;border-radius:50%;background:#e0584f;animation:pulse 1.6s ease-in-out infinite;display:inline-block}}
.card{{background:#0c131e;border:0.5px solid rgba(148,184,200,0.12);border-radius:10px}}
.eyebrow{{font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:0.08em;color:#4BACC6}}
.lbl{{font-size:9px;color:#3d5a70;text-transform:uppercase;letter-spacing:0.04em}}
.tab-bar{{display:inline-flex;background:#0c131e;border:0.5px solid rgba(148,184,200,0.15);border-radius:8px;padding:3px;margin-bottom:1.25rem}}
.tab-btn{{background:none;border:none;color:#7ea8bc;font-size:12px;font-weight:600;padding:9px 16px;cursor:pointer;border-radius:6px}}
.tab-btn.active{{color:#05080d;background:#4BACC6}}
.tab-panel{{display:none}}
.tab-panel.active{{display:block}}
</style></head><body>

<div style="background:#0a1622;border-bottom:0.5px solid rgba(148,184,200,0.12);padding:0 1.5rem;height:50px;display:flex;align-items:center;justify-content:space-between">
<div style="display:flex;align-items:center;gap:10px">
<svg fill="#4BACC6" width="18" height="18" viewBox="0 0 24 24"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
<strong style="font-size:13px;font-weight:600">HEN RT Dispatch Analysis</strong></div>
<div style="display:flex;align-items:center;gap:16px">
<div style="display:flex;align-items:center;gap:6px;font-size:11px;color:#7ea8bc"><span class="livedot"></span><span class="mono">HE{cur_he} · {CDT.strftime('%H:%M CDT')}</span></div>
<a href="results.html" style="font-size:11px;color:#4BACC6;text-decoration:none;border:0.5px solid rgba(75,172,198,0.25);padding:4px 10px;border-radius:5px">← Bid prep</a></div></div>

<div style="max-width:960px;margin:0 auto;padding:1.5rem 1.5rem 3rem">

{run_control_html}

<div style="background:#0c131e;border:0.5px solid rgba({verdict_border_rgba},0.35);border-left:3px solid {verdict_col};border-radius:10px;padding:1rem 1.25rem;margin-bottom:1.25rem;display:flex;align-items:center;justify-content:space-between;gap:1rem">
<div>
<div style="font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:0.08em;color:{verdict_col};margin-bottom:4px">Top signal · right now</div>
<div style="font-size:18px;font-weight:600;letter-spacing:-0.01em">{verdict_action.title()} — {verdict_label}</div>
<div style="font-size:12px;color:#7ea8bc;margin-top:3px">{verdict_sub}</div>
</div>
<div style="text-align:right;flex-shrink:0">
<div class="lbl">RT now</div>
<div class="mono" style="font-size:24px;font-weight:600;color:{verdict_col}">${verdict_rt if verdict_rt is not None else 'N/A'}</div>
</div></div>

<div class="tab-bar">
<button class="tab-btn active" onclick="showTab('outlook',this)">Outlook — HE16–24 + tomorrow AM</button>
<button class="tab-btn" onclick="showTab('overnight',this)">Historical — HE1–15</button>
<button class="tab-btn" onclick="showTab('chart',this)">Charts</button>
</div>

<div class="tab-panel active" id="tab-outlook">

<div class="card" style="padding:1.25rem;margin-bottom:1.25rem">
<div style="display:flex;align-items:center;gap:10px;margin-bottom:14px">
<div style="width:3px;height:14px;background:#4BACC6;border-radius:1px"></div>
<div class="eyebrow">Claude dispatch analysis</div>
<span class="mono" style="font-size:10px;color:#3d5a70;margin-left:auto">{TODAY}</span></div>
{outlook_html}
</div>

<div class="eyebrow" style="margin-bottom:8px;display:block">By zone</div>
<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:1.25rem">
{geo_cards}
</div>

<div class="eyebrow" style="margin-bottom:8px;display:block">Premium nodes (RT-volatile, watched individually)</div>
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:1.25rem">
{premium_cards}
</div>

</div>

<div class="tab-panel" id="tab-overnight">

<div class="card" style="padding:1.25rem;margin-bottom:1.25rem">
<div style="display:flex;align-items:center;gap:10px;margin-bottom:14px">
<div style="width:3px;height:14px;background:#4BACC6;border-radius:1px"></div>
<div class="eyebrow">Congestion debrief</div>
<span class="mono" style="font-size:10px;color:#3d5a70;margin-left:auto">{YESTERDAY} – {TODAY} HE{cur_he}</span></div>
{debrief_html if debrief_html else '<div style="font-size:13px;color:#7ea8bc">No debrief generated this run.</div>'}
</div>

<div class="card" style="padding:1.25rem;margin-bottom:1.25rem;border-color:rgba(224,88,79,0.25)">
<div style="display:flex;align-items:center;gap:10px;margin-bottom:4px">
<div style="width:3px;height:14px;background:#e0584f;border-radius:1px"></div><span class="livedot"></span>
<div class="eyebrow" style="color:#e0584f">RT congestion — live</div>
<span class="mono" style="font-size:10px;color:#3d5a70;margin-left:auto">today · HE1–{cur_he} · {len(sced_rows_t):,} intervals · {len(top_today_constraints)} constraints</span></div>
<div style="font-size:11px;color:#5c7a8c;margin-bottom:12px">Partial day, ranked by total shadow price. HEN-relevant matches use the real shift-factor workbook when available (green name badge); falls back to a name-based guess if a constraint isn't in the workbook yet.</div>
{stacked_html}
{constraint_table(today_rows)}
</div>

<div class="card" style="padding:1.25rem;opacity:0.78">
<div style="display:flex;align-items:center;gap:10px;margin-bottom:4px">
<div style="width:3px;height:14px;background:#3d5a70;border-radius:1px"></div>
<div style="font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:0.08em;color:#7ea8bc">Yesterday's binding constraints</div>
<span class="mono" style="font-size:10px;color:#3d5a70;margin-left:auto">{YESTERDAY} · {len(sced_rows_y):,} intervals · {len(top_constraints)} constraints</span></div>
<div style="font-size:11px;color:#5c7a8c;margin-bottom:12px">Full-day reference — use to anticipate where today's live congestion is headed.</div>
{constraint_table(yesterday_rows)}
</div>

</div>

<div class="tab-panel" id="tab-chart">

<div class="card" style="padding:1.25rem;margin-bottom:1.25rem">
<div style="display:flex;align-items:center;gap:10px;margin-bottom:4px">
<div style="width:3px;height:14px;background:#e0584f;border-radius:1px"></div>
<div class="eyebrow" style="color:#e0584f">Today + tomorrow — RT actuals vs forecast</div>
<span class="livedot" style="margin-left:6px"></span>
<div style="margin-left:auto;display:flex;gap:8px">
<button class="btn" onclick="refreshChart()" style="background:#111f30;border:0.5px solid rgba(75,172,198,0.3);color:#4BACC6;padding:5px 12px;font-size:11px">↺ Refresh</button>
<button class="btn" onclick="toggleFullscreen('today-card')" style="background:#111f30;border:0.5px solid rgba(75,172,198,0.3);color:#4BACC6;padding:5px 12px;font-size:11px">⛶</button>
</div>
</div>
<div style="font-size:11px;color:#5c7a8c;margin-bottom:14px">Solid = forecast · Dashed = RT actual · Red line = now · Click legend items to show/hide · Hover for exact values</div>
<div style="position:relative;height:400px" id="today-card">
<canvas id="today-canvas"></canvas>
</div>
<div id="today-error" style="font-size:12px;color:#e0584f;margin-top:10px;display:none"></div>
</div>

<div class="card" style="padding:1.25rem;margin-bottom:1.25rem" id="chart-card">
<div style="display:flex;align-items:center;gap:10px;margin-bottom:4px">
<div style="width:3px;height:14px;background:#4BACC6;border-radius:1px"></div>
<div class="eyebrow">7-day outlook — load / solar / wind / net load</div>
<span class="mono" style="font-size:10px;color:#3d5a70;margin-left:6px" id="chart-updated">loading...</span>
<div style="margin-left:auto">
<button class="btn" onclick="toggleFullscreen('chart-card')" style="background:#111f30;border:0.5px solid rgba(75,172,198,0.3);color:#4BACC6;padding:5px 12px;font-size:11px">⛶</button>
</div>
</div>
<div style="font-size:11px;color:#5c7a8c;margin-bottom:14px">Solid = forecast · Dashed = RT actual · Click legend to toggle · Hover for values</div>
<div style="position:relative;height:460px" id="chart-container">
<canvas id="outlook-canvas"></canvas>
</div>
<div id="chart-error" style="font-size:12px;color:#e0584f;margin-top:10px;display:none"></div>
</div>

</div>

<div style="text-align:center;font-size:10px;color:#3d5a70;padding:16px 0 0">Data: ERCOT SCED {TODAY} (live) + {YESTERDAY} (full day) · RT prices {TODAY} HE{cur_he} · DA prices {TOMORROW}</div>
</div>

<script>
function showTab(name, btn) {{
  document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
  document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
  document.getElementById("tab-"+name).classList.add("active");
  btn.classList.add("active");
  if (name === 'chart' && !window.chartLoaded) {{
    window.chartLoaded = true;
    if (typeof Chart === 'undefined') {{
      window._chartPending = true;  // onload callback will fire loadOutlookChart when ready
    }} else {{
      loadOutlookChart();
    }}
  }}
}}

let outlookChart = null;
let todayChart = null;

function makeNowPlugin(nowIdx) {{
  return {{
    id: 'nowLine',
    afterDraw(chart) {{
      if (nowIdx < 0) return;
      const {{ctx, chartArea, scales}} = chart;
      const x = scales.x.getPixelForValue(nowIdx);
      ctx.save();
      ctx.strokeStyle = 'rgba(224,88,79,0.7)';
      ctx.lineWidth = 1.5;
      ctx.setLineDash([5,4]);
      ctx.beginPath(); ctx.moveTo(x, chartArea.top); ctx.lineTo(x, chartArea.bottom); ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = '#e0584f';
      ctx.font = 'bold 10px Inter, sans-serif';
      ctx.fillText('now', x + 4, chartArea.top + 14);
      ctx.restore();
    }}
  }};
}}

function chartOptions(pts, nowIdx, tooltipExtra) {{
  return {{
    responsive: true, maintainAspectRatio: false,
    interaction: {{ mode: 'index', intersect: false }},
    plugins: {{
      legend: {{ position: 'top', labels: {{ color: '#94a3b8', boxWidth: 16, font: {{ size: 11 }}, padding: 14 }} }},
      tooltip: {{
        backgroundColor: '#0a1622', borderColor: 'rgba(75,172,198,0.4)', borderWidth: 1,
        titleColor: '#4BACC6', bodyColor: '#c8d8e8', padding: 12,
        callbacks: {{
          title: items => pts[items[0].dataIndex].date + ' HE' + pts[items[0].dataIndex].he,
          label: item => item.raw != null ? ' ' + item.dataset.label + ': ' + (item.raw/1000).toFixed(1) + 'k MW' : null,
          filter: item => item.raw != null,
        }}
      }}
    }},
    scales: {{
      x: {{ ticks: {{ color: '#7ea8bc', font: {{ size: 10 }}, maxRotation: 0, autoSkip: false }}, grid: {{ color: 'rgba(148,184,200,0.06)' }} }},
      y: {{ beginAtZero: false, ticks: {{ color: '#3d5a70', font: {{ size: 10 }}, callback: v => (v/1000).toFixed(0)+'k' }}, grid: {{ color: 'rgba(148,184,200,0.06)' }} }}
    }}
  }};
}}

async function loadOutlookChart() {{
  const errEl = document.getElementById('chart-error');
  const todayErrEl = document.getElementById('today-error');
  errEl.style.display = 'none'; todayErrEl.style.display = 'none';
  try {{
    if (typeof Chart === 'undefined') throw new Error('chart.umd.min.js did not load — is the file in the repo root?');
    const resp = await fetch('chart_data.json?t=' + Date.now());
    if (!resp.ok) throw new Error('chart_data.json not found — has the Chart Data Update workflow run yet?');
    const data = await resp.json();
    document.getElementById('chart-updated').textContent = 'updated ' + data.generated_at;
    const allPts = data.points;
    const nowDate = data.now_date;
    const nowHe = data.now_he;

    // ── Today + Tomorrow chart ──────────────────────────────────────────
    const tomorrow = new Date(nowDate); tomorrow.setDate(tomorrow.getDate()+1);
    const tmrStr = tomorrow.toISOString().slice(0,10);
    const todayPts = allPts.filter(p => p.date === nowDate || p.date === tmrStr);
    const todayNowIdx = todayPts.findIndex(p => p.date === nowDate && p.he === nowHe);
    const todayLabels = todayPts.map(p => p.he === 1 ? p.date.slice(5) : (p.he % 6 === 0 ? 'HE'+p.he : ''));

    const mkT = (key, label, color, dashed) => ({{
      label, data: todayPts.map(p => p[key] != null ? Math.round(p[key]) : null),
      borderColor: color, backgroundColor: 'transparent',
      borderDash: dashed ? [5,4] : [],
      pointRadius: 0, pointHoverRadius: 5, pointHoverBackgroundColor: color,
      borderWidth: dashed ? 1.5 : 2.5, tension: 0.4, spanGaps: true, fill: false,
    }});

    if (todayChart) todayChart.destroy();
    const todayOpts = chartOptions(todayPts, todayNowIdx);
    todayOpts.scales.x.ticks.callback = (val, idx) => todayLabels[idx] || '';
    todayChart = new Chart(document.getElementById('today-canvas'), {{
      type: 'line', plugins: [makeNowPlugin(todayNowIdx)],
      data: {{ labels: todayPts.map((p,i)=>i), datasets: [
        mkT('load_fcst','Total load — fcst','#f472b6',false),
        mkT('load_act','Total load — actual','#f472b6',true),
        mkT('net_load_fcst','Net load — fcst','#94a3b8',false),
        mkT('net_load_act','Net load — actual','#e2e8f0',true),
        mkT('solar_fcst','Solar — fcst','#fbbf24',false),
        mkT('solar_act','Solar — actual','#fde68a',true),
        mkT('wind_fcst','Wind — fcst','#a78bfa',false),
        mkT('wind_act','Wind — actual','#c4b5fd',true),
      ]}},
      options: todayOpts,
    }});

    // ── Weekly outlook chart ────────────────────────────────────────────
    const pts = allPts;
    const nowIdx = pts.findIndex(p => p.date === nowDate && p.he === nowHe);
    const labels = pts.map(p => p.he === 1 ? p.date.slice(5) : '');

    const mkS = (key, label, color, dashed) => ({{
      label, data: pts.map(p => p[key] != null ? Math.round(p[key]) : null),
      borderColor: color, backgroundColor: 'transparent',
      borderDash: dashed ? [5,4] : [],
      pointRadius: 0, pointHoverRadius: 5, pointHoverBackgroundColor: color,
      borderWidth: dashed ? 1.5 : 2.5, tension: 0.4, spanGaps: true, fill: false,
    }});

    if (outlookChart) outlookChart.destroy();
    const weekOpts = chartOptions(pts, nowIdx);
    weekOpts.scales.x.ticks.callback = (val, idx) => labels[idx] || '';
    outlookChart = new Chart(document.getElementById('outlook-canvas'), {{
      type: 'line', plugins: [makeNowPlugin(nowIdx)],
      data: {{ labels: pts.map((p,i)=>i), datasets: [
        mkS('load_fcst','Total load — fcst','#f472b6',false),
        mkS('load_act','Total load — actual','#f472b6',true),
        mkS('net_load_fcst','Net load — fcst','#94a3b8',false),
        mkS('net_load_act','Net load — actual','#e2e8f0',true),
        mkS('solar_fcst','Solar — fcst','#fbbf24',false),
        mkS('solar_act','Solar — actual','#fde68a',true),
        mkS('wind_fcst','Wind — fcst','#a78bfa',false),
        mkS('wind_act','Wind — actual','#c4b5fd',true),
        mkS('hsl_outage','HSL outages','#34d399',false),
      ]}},
      options: weekOpts,
    }});

  }} catch (err) {{
    errEl.style.display = 'block';
    errEl.textContent = 'Could not load chart: ' + err.message;
  }}
}}

async function refreshChart() {{
  if (outlookChart) {{ outlookChart.destroy(); outlookChart = null; }}
  if (todayChart) {{ todayChart.destroy(); todayChart = null; }}
  document.getElementById('chart-updated').textContent = 'refreshing...';
  await loadOutlookChart();
}}

function toggleFullscreen(elId) {{
  const el = document.getElementById(elId);
  if (!document.fullscreenElement) {{
    el.requestFullscreen().then(() => {{
      el.style.background = '#05080d';
      el.style.padding = '1rem';
      if (outlookChart) outlookChart.resize();
      if (todayChart) todayChart.resize();
    }});
  }} else {{
    document.exitFullscreen().then(() => {{
      el.style.background = ''; el.style.padding = '';
      if (outlookChart) outlookChart.resize();
      if (todayChart) todayChart.resize();
    }});
  }}
}}

const OWNER = 'wkight23';
const REPO = 'hen-dashboard';
const WORKFLOW = 'rt-analysis.yml';

function saveToken() {{
  const t = document.getElementById('gh-token').value.trim();
  if (!t.startsWith('ghp_') && !t.startsWith('github_pat_')) {{
    document.getElementById('token-status').textContent = 'Token should start with ghp_ or github_pat_';
    document.getElementById('token-status').style.color = '#e0584f';
    return;
  }}
  sessionStorage.setItem('gh_token', t);
  document.getElementById('token-status').textContent = '✓ Token saved for this session';
  document.getElementById('token-status').style.color = '#4fcf8a';
  document.getElementById('gh-token').value = '';
}}

async function runAnalysis() {{
  const token = sessionStorage.getItem('gh_token');
  if (!token) {{ alert('Please enter your GitHub token first.'); return; }}
  const btn = document.getElementById('run-btn');
  const status = document.getElementById('status-msg');
  const progress = document.getElementById('progress-bar');
  const fill = document.getElementById('progress-fill');
  btn.disabled = true; btn.textContent = '⚡ Triggering...';
  progress.style.display = 'block'; fill.style.width = '5%';
  try {{
    const triggerResp = await fetch(`https://api.github.com/repos/${{OWNER}}/${{REPO}}/actions/workflows/${{WORKFLOW}}/dispatches`,
      {{method:'POST', headers:{{'Authorization':`token ${{token}}`,'Accept':'application/vnd.github.v3+json','Content-Type':'application/json'}}, body: JSON.stringify({{ref:'main'}})}});
    if (!triggerResp.ok) throw new Error(`Trigger failed: ${{triggerResp.status}}`);
    status.textContent = 'Workflow triggered. Waiting for it to start...'; fill.style.width = '15%';
    await new Promise(r => setTimeout(r, 5000)); fill.style.width = '25%';
    let elapsed = 0;
    while (elapsed < 180) {{
      await new Promise(r => setTimeout(r, 5000)); elapsed += 5;
      const runsResp = await fetch(`https://api.github.com/repos/${{OWNER}}/${{REPO}}/actions/workflows/${{WORKFLOW}}/runs?per_page=1`,
        {{headers:{{'Authorization':`token ${{token}}`,'Accept':'application/vnd.github.v3+json'}}}});
      const runsData = await runsResp.json();
      const run = runsData.workflow_runs && runsData.workflow_runs[0];
      if (run) {{
        const pct = Math.min(90, 30 + (elapsed/180)*60);
        fill.style.width = `${{pct}}%`;
        status.textContent = `Running... ${{elapsed}}s elapsed (${{run.status}})`;
        if (run.status === 'completed') {{
          if (run.conclusion === 'success') {{
            fill.style.width = '100%'; fill.style.background = '#4fcf8a';
            status.textContent = '✓ Analysis complete! Reloading...';
            setTimeout(() => {{ window.location.href = 'rt.html?t=' + Date.now(); }}, 2000);
          }} else {{
            fill.style.background = '#e0584f';
            status.textContent = `Run ended with: ${{run.conclusion}}. Check GitHub Actions for details.`;
            btn.disabled = false; btn.textContent = '⚡ Run analysis';
          }}
          return;
        }}
      }}
    }}
    status.textContent = 'Timed out waiting. Check GitHub Actions tab for status.';
    btn.disabled = false; btn.textContent = '⚡ Run analysis';
  }} catch (err) {{
    status.textContent = 'Error: ' + err.message; status.style.color = '#e0584f';
    btn.disabled = false; btn.textContent = '⚡ Run analysis';
  }}
}}

if (sessionStorage.getItem('gh_token')) {{
  document.getElementById('token-status').textContent = '✓ Token loaded from session';
  document.getElementById('token-status').style.color = '#4fcf8a';
}}
</script>
</body></html>"""

with open("rt.html","w") as f:
    f.write(html)
print(f"Done. Constraints today:{len(top_today_constraints)} yesterday:{len(top_constraints)} RT_nodes:{len(rt_prices)} DA_nodes:{len(da_prices)} verdict:{verdict_action} {verdict_label}")
