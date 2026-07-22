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

# np4-742-cd: Wind by Geographical Region — Panhandle/North, West, South/Houston
# Field names printed on first run so we can confirm column matches
print("Fetching regional wind (np4-742-cd)...")
wind_geo = {}
try:
    r = requests.get(BASE+"/np4-742-cd/wpp_hrly_actual_fcast_geo",
        params={"deliveryDateFrom":START_DATE,"deliveryDateTo":END_DATE,"size":5000},
        headers=hdrs, timeout=30)
    if r.ok:
        d = r.json()
        fields = d.get("fields",[])
        rows = d.get("data",[])
        print(f"Wind geo: fields = {[f.get('name') for f in fields]}")
        date_col = next((f["cardinality"]-1 for f in fields if "deliverydate" in f.get("name","").lower()), 1)
        hour_col = next((f["cardinality"]-1 for f in fields if "hour" in f.get("name","").lower()), 2)
        # Try to find columns for each region — print all field names to log so we can verify
        def find_col(fields, *keywords):
            kw = [k.lower() for k in keywords]
            return next((f["cardinality"]-1 for f in fields if all(k in f.get("name","").lower() for k in kw)), None)
        cols = {
            "pan_act":  find_col(fields, "panhandle", "gen"),
            "pan_fcst": find_col(fields, "panhandle", "stwpf"),
            "west_act": find_col(fields, "west", "gen"),
            "west_fcst":find_col(fields, "west", "stwpf"),
            "sh_act":   find_col(fields, "south", "gen"),
            "sh_fcst":  find_col(fields, "south", "stwpf"),
        }
        print(f"Wind geo col matches: {cols}")
        for row in rows:
            if not isinstance(row, list): continue
            try:
                d_str = str(row[date_col])[:10]
                he = parse_he(row[hour_col]) if hour_col < len(row) else 0
                entry = {}
                for key, col in cols.items():
                    if col is not None and col < len(row) and row[col] not in (None,""):
                        entry[key] = float(row[col])
                if entry: wind_geo[(d_str, he)] = entry
            except: continue
        print(f"Wind geo: {len(wind_geo)} hourly rows parsed")
    else:
        print(f"Wind geo: request failed with status {r.status_code}")
except Exception as e:
    print(f"Wind geo: error {e}")

# ─── HSL outages: sum all four zone columns ───
outages = fetch_outages()

# ─── Assemble one combined hourly series ───
CHART_START = (TODAY - timedelta(days=1)).isoformat()  # yesterday
CHART_END = END_DATE                                    # 7 days ahead

all_keys = set(load_fcst) | set(load_act) | set(solar) | set(wind) | set(outages) | set(wind_geo)
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
    wg = wind_geo.get((d_str,he), {})
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
        # Regional load (forecast)
        "load_north_fcst": reg_f.get("north"), "load_south_fcst": reg_f.get("south"),
        "load_west_fcst":  reg_f.get("west"),  "load_houston_fcst": reg_f.get("houston"),
        # Regional load (actual — only past hours)
        "load_north_act":   None if is_future else reg_a.get("north"),
        "load_south_act":   None if is_future else reg_a.get("south"),
        "load_west_act":    None if is_future else reg_a.get("west"),
        "load_houston_act": None if is_future else reg_a.get("houston"),
        # Regional wind (from np4-742-cd)
        "wind_pan_fcst":  wg.get("pan_fcst"), "wind_pan_act":  None if is_future else wg.get("pan_act"),
        "wind_west_fcst": wg.get("west_fcst"),"wind_west_act": None if is_future else wg.get("west_act"),
        "wind_sh_fcst":   wg.get("sh_fcst"),  "wind_sh_act":   None if is_future else wg.get("sh_act"),
    })

chart_data = {
    "generated_at": CDT.strftime("%Y-%m-%d %H:%M CDT"),
    "now_date": TODAY.isoformat(),
    "now_he": CDT.hour + 1,
    "points": points
}
with open("chart_data.json", "w") as f:
    json.dump(chart_data, f)
print(f"Done. {len(points)} hourly points written to chart_data.json")
