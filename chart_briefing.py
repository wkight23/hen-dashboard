import os, json, requests, time
from datetime import datetime, date, timedelta, timezone

ERCOT_USER = os.environ["ERCOT_USERNAME"]
ERCOT_PASS = os.environ["ERCOT_PASSWORD"]
ERCOT_SUBKEY = os.environ["ERCOT_SUBKEY"]
BASE = "https://api.ercot.com/api/public-reports"
AUTH_URL = "https://ercotb2c.b2clogin.com/ercotb2c.onmicrosoft.com/B2C_1_PUBAPI-ROPC-FLOW/oauth2/v2.0/token"

CDT = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=5)
TODAY = CDT.date()
START_DATE = (TODAY - timedelta(days=1)).isoformat()   # yesterday
END_DATE = (TODAY + timedelta(days=7)).isoformat()      # 7 days ahead

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

def fetch_series(endpoint, label, want_cols, extra_params=None):
    """Fetch an hourly ERCOT report and pull out the requested columns by best-effort name match.
    want_cols: dict of {result_key: [substrings to look for in the field name, case-insensitive]}
    Returns {(date_str, hour): {result_key: value}}"""
    out = {}
    base_params = {"deliveryDateFrom":START_DATE,"deliveryDateTo":END_DATE,"page":1,"size":5000}
    if extra_params:
        base_params.update(extra_params)
    base_params = {k:v for k,v in base_params.items() if v is not None}
    for page in range(1, 6):
        try:
            params = {**base_params, "page": page}
            r = requests.get(BASE+endpoint, params=params, headers=hdrs, timeout=30)
            if not r.ok:
                print(f"{label}: request failed with status {r.status_code}")
                break
            d = r.json()
            fields = d.get("fields",[])
            rows = d.get("data",[])
            if page == 1:
                print(f"{label}: fields = {[f.get('name') for f in fields]}")
            # Date column: handle deliveryDate, operatingDay, operatingDate
            date_col = next((f["cardinality"]-1 for f in fields
                            if f.get("name","").lower() in ("deliverydate","operatingday","operatingdate","date")), 1)
            hour_col = next((f["cardinality"]-1 for f in fields
                            if "hour" in f.get("name","").lower()), 2)
            col_map = {}
            for key, needles in want_cols.items():
                col_map[key] = next((f["cardinality"]-1 for f in fields
                                    if all(n.lower() in f.get("name","").lower() for n in needles)), None)
            sample_printed = False
            for row in rows:
                if not isinstance(row, list): continue
                try:
                    raw_date = str(row[date_col])
                    # Normalize: handle both YYYY-MM-DD and MM/DD/YYYY formats
                    if len(raw_date) >= 10 and raw_date[2] == '/' and raw_date[5] == '/':
                        # MM/DD/YYYY → YYYY-MM-DD
                        parts = raw_date[:10].split('/')
                        d_str = f"{parts[2]}-{parts[0]:0>2}-{parts[1]:0>2}"
                    else:
                        d_str = raw_date[:10]
                    if not sample_printed and page == 1:
                        print(f"{label} date sample: raw={raw_date!r} → normalized={d_str!r}")
                        sample_printed = True
                    he = parse_he(row[hour_col]) if hour_col < len(row) else 0
                    key = (d_str, he)
                    entry = out.setdefault(key, {})
                    for rkey, col in col_map.items():
                        if col is not None and col < len(row) and row[col] not in (None, ""):
                            try: entry[rkey] = float(row[col])
                            except: pass
                except: continue
            if len(rows) < 5000: break
        except Exception as e:
            print(f"{label}: error {e}")
            break
    print(f"{label}: {len(out)} hourly rows parsed")
    return out

def fetch_outages():
    """Fetch hourly resource outage capacity and sum all four ERCOT zone columns."""
    out = {}
    ZONE_COLS = ["totalResourceMWZoneSouth","totalResourceMWZoneNorth",
                 "totalResourceMWZoneWest","totalResourceMWZoneHouston"]
    try:
        r = requests.get(BASE+"/np3-233-cd/hourly_res_outage_cap",
            params={"size":5000}, headers=hdrs, timeout=30)
        if not r.ok:
            print(f"HSL outages: request failed with status {r.status_code}")
            return out
        d = r.json()
        fields = d.get("fields",[])
        rows = d.get("data",[])
        print(f"HSL outages: fields = {[f.get('name') for f in fields]}")
        date_col = next((f["cardinality"]-1 for f in fields
                        if f.get("name","").lower() in ("operatingdate","operatingday","deliverydate")), 1)
        hour_col = next((f["cardinality"]-1 for f in fields if "hour" in f.get("name","").lower()), 2)
        zone_col_idxs = [f["cardinality"]-1 for f in fields if f.get("name","") in ZONE_COLS]
        for row in rows:
            if not isinstance(row, list): continue
            try:
                d_str = str(row[date_col])[:10]
                he = parse_he(row[hour_col]) if hour_col < len(row) else 0
                total_mw = sum(float(row[i]) for i in zone_col_idxs if i < len(row) and row[i] not in (None,""))
                if total_mw: out[(d_str, he)] = {"mw": total_mw}
            except: continue
    except Exception as e:
        print(f"HSL outages: error {e}")
    print(f"HSL outages: {len(out)} hourly rows parsed")
    return out

# ─── Load: forecast (7-day) + actual — total AND regional breakdown ───
# North  = north + northCentral
# South  = southCentral + southern
# West   = farWest + west
# Houston= coast + east
LOAD_ZONE_FIELDS = {"coast","east","farWest","north","northCentral","southCentral","southern","west"}
FCST_ZONE_GROUP  = {"coast":"houston","east":"houston","farWest":"west","north":"north",
                    "northCentral":"north","southCentral":"south","southern":"south","west":"west"}
print("Fetching load forecast...")
load_fcst = {}
load_fcst_reg = {}   # regional grouped forecast
try:
    for page in range(1, 6):
        r = requests.get(BASE+"/np3-565-cd/lf_by_model_weather_zone",
            params={"deliveryDateFrom":START_DATE,"deliveryDateTo":END_DATE,"page":page,"size":5000},
            headers=hdrs, timeout=30)
        if not r.ok:
            print(f"Load forecast: request failed with status {r.status_code}")
            break
        d = r.json()
        fields = d.get("fields",[])
        rows = d.get("data",[])
        if page == 1:
            print(f"Load forecast: fields = {[f.get('name') for f in fields]}")
        date_col  = next((f["cardinality"]-1 for f in fields if "deliverydate" in f.get("name","").lower()), 1)
        hour_col  = next((f["cardinality"]-1 for f in fields if "hour" in f.get("name","").lower()), 2)
        flag_col  = next((f["cardinality"]-1 for f in fields if "inuse" in f.get("name","").lower()), None)
        zone_col_map = {f.get("name",""): f["cardinality"]-1 for f in fields if f.get("name","") in LOAD_ZONE_FIELDS}
        zone_cols = list(zone_col_map.values())
        sample_printed = False
        for row in rows:
            if not isinstance(row, list): continue
            try:
                if flag_col is not None and flag_col < len(row):
                    flag = str(row[flag_col]).strip().lower()
                    if flag not in ("true","1","yes"): continue
                d_str = str(row[date_col])[:10]
                he = parse_he(row[hour_col]) if hour_col < len(row) else 0
                total_mw = sum(float(row[i]) for i in zone_cols if i < len(row) and row[i] not in (None,""))
                if total_mw > 0:
                    load_fcst[(d_str, he)] = {"load": total_mw}
                    # Build regional grouped totals
                    reg = {"north": 0.0, "south": 0.0, "west": 0.0, "houston": 0.0}
                    for zname, col in zone_col_map.items():
                        if col < len(row) and row[col] not in (None,""):
                            grp = FCST_ZONE_GROUP.get(zname)
                            if grp: reg[grp] += float(row[col])
                    load_fcst_reg[(d_str, he)] = reg
                    if not sample_printed and page == 1:
                        print(f"Load forecast sample: date={d_str} HE{he} total={total_mw:.0f} MW N={reg['north']:.0f} S={reg['south']:.0f} W={reg['west']:.0f} H={reg['houston']:.0f}")
                        sample_printed = True
            except: continue
        if len(rows) < 5000: break
except Exception as e:
    print(f"Load forecast: error {e}")
print(f"Load forecast: {len(load_fcst)} hourly rows parsed")

# Actual load — np6-345-cd + regional breakdown
# Actual zones: coast, east, farWest, north, northC, southern, southC, west
ACT_ZONE_GROUP = {"coast":"houston","east":"houston","farWest":"west","north":"north",
                  "northC":"north","southC":"south","southern":"south","west":"west"}
ACT_ZONE_FIELDS = set(ACT_ZONE_GROUP.keys())
load_act = {}
load_act_reg = {}
try:
    r = requests.get(BASE+"/np6-345-cd/act_sys_load_by_wzn",
        params={"size":5000}, headers=hdrs, timeout=30)
    if r.ok:
        d = r.json()
        fields = d.get("fields",[])
        rows = d.get("data",[])
        print(f"Load actual: fields = {[f.get('name') for f in fields]}")
        date_col = next((f["cardinality"]-1 for f in fields if f.get("name","").lower() in ("operatingday","operatingdate","deliverydate")), 0)
        hour_col = next((f["cardinality"]-1 for f in fields if "hour" in f.get("name","").lower()), 1)
        total_col = next((f["cardinality"]-1 for f in fields if f.get("name","").lower() == "total"), None)
        zone_col_map_act = {f.get("name",""): f["cardinality"]-1 for f in fields if f.get("name","") in ACT_ZONE_FIELDS}
        for row in rows:
            if not isinstance(row, list): continue
            try:
                raw = str(row[date_col])
                d_str = f"{raw[6:10]}-{raw[0:2]}-{raw[3:5]}" if len(raw) >= 10 and raw[2] == '/' else raw[:10]
                he = parse_he(row[hour_col]) if hour_col < len(row) else 0
                if total_col is not None and total_col < len(row) and row[total_col] not in (None,""):
                    load_act[(d_str, he)] = {"load": float(row[total_col])}
                reg = {"north": 0.0, "south": 0.0, "west": 0.0, "houston": 0.0}
                for zname, col in zone_col_map_act.items():
                    if col < len(row) and row[col] not in (None,""):
                        grp = ACT_ZONE_GROUP.get(zname)
                        if grp: reg[grp] += float(row[col])
                if any(v > 0 for v in reg.values()):
                    load_act_reg[(d_str, he)] = reg
            except: continue
        print(f"Load actual: {len(load_act)} hourly rows parsed")
    else:
        print(f"Load actual: request failed with status {r.status_code}")
except Exception as e:
    print(f"Load actual: error {e}")

# ─── Solar: genSystemWide = actual, STPPFSystemWide = forecast (confirmed) ───
solar = fetch_series("/np4-737-cd/spp_hrly_avrg_actl_fcast", "Solar actual+forecast",
    {"actual": ["genSystemWide"], "forecast": ["STPPFSystemWide"]})

# ─── Wind: total from np4-732-cd + regional from np4-742-cd ───
wind = fetch_series("/np4-732-cd/wpp_hrly_avrg_actl_fcast", "Wind actual+forecast",
    {"actual": ["genSystemWide"], "forecast": ["STWPFSystemWide"]})

# np4-742-cd: Wind by Geographical Region (hourly) — confirmed fields:
# genPanhandle, STWPFPanhandle, genCoastal, STWPFCoastal, genSouth, STWPFSouth,
# genWest, STWPFWest, genNorth, STWPFNorth
print("Fetching regional wind hourly (np4-742-cd)...")
wind_geo_fcst = {}
try:
    r = requests.get(BASE+"/np4-742-cd/wpp_hrly_actual_fcast_geo",
        params={"deliveryDateFrom":START_DATE,"deliveryDateTo":END_DATE,"size":5000},
        headers=hdrs, timeout=30)
    if r.ok:
        d = r.json()
        fields = d.get("fields",[])
        rows = d.get("data",[])
        print(f"Wind geo hourly: fields = {[f.get('name') for f in fields]}")
        date_col = next((f["cardinality"]-1 for f in fields if "deliverydate" in f.get("name","").lower()), 1)
        hour_col = next((f["cardinality"]-1 for f in fields if "hour" in f.get("name","").lower()), 2)
        # Confirmed field names from ERCOT API spec
        WIND_GEO_COLS = {
            "pan_fcst": "STWPFPanhandle", "pan_act": "genPanhandle",
            "coastal_fcst": "STWPFCoastal", "coastal_act": "genCoastal",
            "south_fcst": "STWPFSouth", "south_act": "genSouth",
            "west_fcst": "STWPFWest", "west_act": "genWest",
            "north_fcst": "STWPFNorth", "north_act": "genNorth",
        }
        col_idxs = {k: next((f["cardinality"]-1 for f in fields if f.get("name","") == v), None)
                    for k, v in WIND_GEO_COLS.items()}
        print(f"Wind geo hourly col matches: {col_idxs}")
        for row in rows:
            if not isinstance(row, list): continue
            try:
                d_str = str(row[date_col])[:10]
                he = parse_he(row[hour_col]) if hour_col < len(row) else 0
                entry = {}
                for key, col in col_idxs.items():
                    if col is not None and col < len(row) and row[col] not in (None,""):
                        entry[key] = float(row[col])
                if entry: wind_geo_fcst[(d_str, he)] = entry
            except: continue
        print(f"Wind geo hourly: {len(wind_geo_fcst)} hourly rows parsed")
    else:
        print(f"Wind geo hourly: request failed with status {r.status_code}")
except Exception as e:
    print(f"Wind geo hourly: error {e}")

# np4-743-cd: Wind 5-minute actual values by geographical region
# Uses postedDatetimeFrom (not deliveryDateFrom) and intervalEnding (not hourEnding)
# Same geographical regions as np4-742-cd
print("Fetching regional wind 5-min actual (np4-743-cd)...")
wind_geo_5min = {}
try:
    # Fetch last 24 hours of 5-minute data for today's actuals
    ts_from = (CDT - timedelta(days=1)).strftime("%Y-%m-%dT00:00:00")
    r = requests.get(BASE+"/np4-743-cd/wpp_actual_5min_avg_values_geo",
        params={"postedDatetimeFrom":ts_from,"size":5000},
        headers=hdrs, timeout=30)
    if r.ok:
        d = r.json()
        fields = d.get("fields",[])
        rows = d.get("data",[])
        print(f"Wind geo 5min: fields = {[f.get('name') for f in fields]}")
        ts_col = next((f["cardinality"]-1 for f in fields if "interval" in f.get("name","").lower() or "posted" in f.get("name","").lower()), 0)
        # 5-min endpoint uses lowercase region names without "gen" prefix
        WIND_5MIN_COLS = {
            "pan_act": "panhandle", "coastal_act": "coastal",
            "south_act": "south", "west_act": "west", "north_act": "north",
        }
        col_idxs_5m = {k: next((f["cardinality"]-1 for f in fields if f.get("name","") == v), None)
                       for k, v in WIND_5MIN_COLS.items()}
        # Use intervalEnding (not postedDatetime) for the interval timestamp
        ts_col = next((f["cardinality"]-1 for f in fields if "intervalending" in f.get("name","").lower()),
                      next((f["cardinality"]-1 for f in fields if "interval" in f.get("name","").lower()), 0))
        sample_printed = False
        for row in rows:
            if not isinstance(row, list): continue
            try:
                # 5-min data uses interval timestamps — extract date and 5-min interval
                ts = str(row[ts_col]) if ts_col < len(row) else ""
                if "T" in ts:
                    d_str = ts[:10]
                    time_part = ts[11:16]  # HH:MM
                    h, m = int(time_part[:2]), int(time_part[3:5])
                    interval_key = (d_str, h, m)  # store at 5-min granularity
                else:
                    continue
                entry = {}
                for key, col in col_idxs_5m.items():
                    if col is not None and col < len(row) and row[col] not in (None,""):
                        entry[key] = float(row[col])
                if entry:
                    wind_geo_5min[interval_key] = entry
                    if not sample_printed:
                        print(f"Wind geo 5min sample: {interval_key} = {entry}")
                        sample_printed = True
            except: continue
        print(f"Wind geo 5min: {len(wind_geo_5min)} 5-minute intervals parsed")
    else:
        print(f"Wind geo 5min: request failed with status {r.status_code}")
except Exception as e:
    print(f"Wind geo 5min: error {e}")

# ─── HSL outages: sum all four zone columns ───
outages = fetch_outages()

# ─── DA Settlement Point Prices — today + tomorrow, all 32 fleet nodes + 4 zone hubs ───
DA_NODES = [
    # Zone hubs — used as DA reference price for all non-premium batteries in each zone
    "LZ_WEST","LZ_NORTH","LZ_SOUTH","LZ_HOUSTON",
    # Premium nodes — individually registered DA settlement points
    "CATARINA_B1","HOLCOMB_RN1","HAMI_BESS_RN","JUNCTION_RN","RUSSEKST_RN","FTDUNCAN_RN",
]
DA_DATE_FROM = TODAY.isoformat()
DA_DATE_TO   = (TODAY + timedelta(days=1)).isoformat()

print(f"Fetching DA prices for {len(DA_NODES)} settlement points ({DA_DATE_FROM} + {DA_DATE_TO})...")
da_prices = {}
da_fetched = 0
da_failed = []
for idx, node in enumerate(DA_NODES):
    # Re-authenticate every 15 nodes to keep the token fresh during long runs
    if idx > 0 and idx % 15 == 0:
        try:
            auth_resp2 = requests.post(AUTH_URL, data={"username":ERCOT_USER,"password":ERCOT_PASS,"grant_type":"password","scope":"openid fec253ea-0d06-4272-a5e6-b478baeecd70 offline_access","client_id":"fec253ea-0d06-4272-a5e6-b478baeecd70","response_type":"id_token"})
            token2 = auth_resp2.json().get("id_token","")
            if token2: hdrs["Authorization"] = "Bearer " + token2
            print(f"Re-authenticated at node #{idx}")
        except: pass
    try:
        r = requests.get(BASE+"/np4-190-cd/dam_stlmnt_pnt_prices",
            params={"settlementPoint":node,"deliveryDateFrom":DA_DATE_FROM,"deliveryDateTo":DA_DATE_TO,"size":50},
            headers=hdrs, timeout=15)
        if r.ok:
            d = r.json()
            fields = d.get("fields",[])
            rows = d.get("data",[])
            date_col  = next((f["cardinality"]-1 for f in fields if "deliverydate" in f.get("name","").lower()), 0)
            hour_col  = next((f["cardinality"]-1 for f in fields if "hour" in f.get("name","").lower()), 2)
            price_col = next((f["cardinality"]-1 for f in fields if "price" in f.get("name","").lower()), 4)
            node_data = {}
            for row in rows:
                if not isinstance(row, list): continue
                try:
                    d_str = str(row[date_col])[:10]
                    he    = parse_he(row[hour_col]) if hour_col < len(row) else 0
                    price = float(row[price_col]) if price_col < len(row) and row[price_col] not in (None,"") else None
                    if price is not None:
                        node_data.setdefault(d_str, {})[he] = round(price, 2)
                except: continue
            if node_data:
                da_prices[node] = node_data
                da_fetched += 1
            else:
                da_failed.append(node)
        else:
            da_failed.append(node)
        time.sleep(0.5)   # 0.5s delay — ERCOT API rate limits at ~30 req/min
    except Exception as e:
        da_failed.append(node)
        time.sleep(0.5)
if da_failed:
    print(f"DA prices: {da_fetched}/{len(DA_NODES)} fetched. Failed nodes: {da_failed[:5]}{'...' if len(da_failed)>5 else ''}")
else:
    print(f"DA prices: {da_fetched}/{len(DA_NODES)} nodes fetched successfully")

# ─── Assemble one combined hourly series ───
CHART_START = (TODAY - timedelta(days=1)).isoformat()  # yesterday
CHART_END = END_DATE                                    # 7 days ahead

all_keys = set(load_fcst) | set(load_act) | set(solar) | set(wind) | set(outages) | set(wind_geo_fcst)
points = []
for d_str, he in sorted(all_keys):
    if d_str < CHART_START or d_str > CHART_END:
        continue
    is_future = d_str > CDT.date().isoformat() or (d_str == CDT.date().isoformat() and he > CDT.hour + 1)
    lf = load_fcst.get((d_str,he), {}).get("load")
    la = load_act.get((d_str,he), {}).get("load")
    sf = solar.get((d_str,he), {}).get("forecast")
    sa = solar.get((d_str,he), {}).get("actual")
    wf = wind.get((d_str,he), {}).get("forecast")
    wa = wind.get((d_str,he), {}).get("actual")
    out_mw = outages.get((d_str,he), {}).get("mw")
    reg_f = load_fcst_reg.get((d_str,he), {})
    reg_a = load_act_reg.get((d_str,he), {})
    wg = wind_geo_fcst.get((d_str,he), {})

    # For wind actuals, prefer the most recent 5-minute reading within the hour
    # Find the latest 5-min interval within this hour
    def best_5min(region_key):
        best = None
        for m in [55,50,45,40,35,30,25,20,15,10,5,0]:
            v = wind_geo_5min.get((d_str, he-1, m))  # he-1 because interval ends at :mm within the hour
            if v is None: v = wind_geo_5min.get((d_str, he if he < 24 else 0, m))
            if v and region_key in v:
                best = v[region_key]; break
        return best

    net_fcst = (lf - sf - wf) if (lf is not None and sf is not None and wf is not None) else None
    net_act = (la - sa - wa) if (not is_future and la is not None and sa is not None and wa is not None) else None
    points.append({
        "date": d_str, "he": he,
        # Total ERCOT
        "load_fcst": lf, "load_act": None if is_future else la,
        "solar_fcst": sf, "solar_act": None if is_future else sa,
        "wind_fcst": wf, "wind_act": None if is_future else wa,
        "net_load_fcst": net_fcst, "net_load_act": net_act,
        "hsl_outage": out_mw,
        # Regional load forecast
        "load_north_fcst": reg_f.get("north"), "load_south_fcst": reg_f.get("south"),
        "load_west_fcst":  reg_f.get("west"),  "load_houston_fcst": reg_f.get("houston"),
        # Regional load actual
        "load_north_act":   None if is_future else reg_a.get("north"),
        "load_south_act":   None if is_future else reg_a.get("south"),
        "load_west_act":    None if is_future else reg_a.get("west"),
        "load_houston_act": None if is_future else reg_a.get("houston"),
        # Regional wind forecast (hourly, from np4-742-cd)
        "wind_pan_fcst":     wg.get("pan_fcst"),
        "wind_coastal_fcst": wg.get("coastal_fcst"),
        "wind_south_fcst":   wg.get("south_fcst"),
        "wind_west_fcst":    wg.get("west_fcst"),
        "wind_north_fcst":   wg.get("north_fcst"),
        # Regional wind actual — 5-min where available, hourly hourly as fallback
        "wind_pan_act":     None if is_future else (best_5min("pan_act") or wg.get("pan_act")),
        "wind_coastal_act": None if is_future else (best_5min("coastal_act") or wg.get("coastal_act")),
        "wind_south_act":   None if is_future else (best_5min("south_act") or wg.get("south_act")),
        "wind_west_act":    None if is_future else (best_5min("west_act") or wg.get("west_act")),
        "wind_north_act":   None if is_future else (best_5min("north_act") or wg.get("north_act")),
    })

chart_data = {
    "generated_at": CDT.strftime("%Y-%m-%d %H:%M CDT"),
    "now_date": TODAY.isoformat(),
    "now_he": CDT.hour + 1,
    "da_today": DA_DATE_FROM,
    "da_tomorrow": DA_DATE_TO,
    "da_prices": da_prices,
    "points": points
}
with open("chart_data.json", "w") as f:
    json.dump(chart_data, f)
print(f"Done. {len(points)} hourly points written to chart_data.json")
