import os, json, requests
from datetime import datetime, date
ERCOT_USER = os.environ["ERCOT_USERNAME"]
ERCOT_PASS = os.environ["ERCOT_PASSWORD"]
ERCOT_SUBKEY = os.environ["ERCOT_SUBKEY"]
ANTHROPIC_KEY = os.environ["ANTHROPIC_API_KEY"]
BASE = "https://api.ercot.com/api/public-reports"
AUTH_URL = "https://ercotb2c.b2clogin.com/ercotb2c.onmicrosoft.com/B2C_1_PUBAPI-ROPC-FLOW/oauth2/v2.0/token"
TODAY = date.today().isoformat()
NOW = datetime.now()
MODE = "da" if NOW.hour >= 13 else "morning"
print("Authenticating with ERCOT...")
auth_resp = requests.post(AUTH_URL, data={"username": ERCOT_USER, "password": ERCOT_PASS, "grant_type": "password", "scope": "openid fec253ea-0d06-4272-a5e6-b478baeecd70 offline_access", "client_id": "fec253ea-0d06-4272-a5e6-b478baeecd70", "response_type": "id_token"})
token = auth_resp.json().get("id_token", "")
hdrs = {"Authorization": "Bearer " + token, "Ocp-Apim-Subscription-Key": ERCOT_SUBKEY}
print("Fetching ERCOT data...")
def eg(path):
    try:
        r = requests.get(BASE + "/" + path + "?deliveryDateFrom=" + TODAY + "&deliveryDateTo=" + TODAY + "&size=500", headers=hdrs, timeout=30)
        return r.json() if r.ok else {}
    except:
        return {}
wind_data = eg("np4-742-cd/wpp_hrly_actual_fcast_geo")
load_data = eg("np3-565-cd/lf_by_model_weather_zone")
solar_data = eg("np4-737-cd/spp_hrly_avrg_actl_fcast")
shadow_data = eg("np4-191-cd/dam_shadow_prices") if MODE == "da" else {}
def avg(lst): return sum(lst)/len(lst)/1000 if lst else 0
def mx(lst): return max(lst)/1000 if lst else 0
items = wind_data.get("_embedded", {}).get("wpp_hrly_actual_fcast_geo", wind_data.get("data", []))
br = {"WEST": [], "SOUTH": [], "COASTAL": [], "PANHANDLE": []}
for r in items:
    if not isinstance(r, dict): continue
    rg = (r.get("genRegion") or r.get("region") or "").upper()
    v = float(r.get("hourlyWindGenForecast") or r.get("genForecast") or 0)
    if rg in br and v > 0: br[rg].append(v)
wind = {"west": avg(br["WEST"]), "south": avg(br["SOUTH"]), "coastal": avg(br["COASTAL"]), "pan": avg(br["PANHANDLE"])}
wind["total"] = wind["west"] + wind["south"] + wind["coastal"] + wind["pan"]
sol = solar_data.get("_embedded", {}).get("spp_hrly_avrg_actl_fcast", solar_data.get("data", []))
sv = [float(r.get("hourlySystemGenForecast") or 0) for r in sol if isinstance(r, dict) and float(r.get("hourlySystemGenForecast") or 0) > 0]
wind["solar"] = max(sv)/1000 if sv else 0
li = load_data.get("_embedded", {}).get("lf_by_model_weather_zone", load_data.get("data", []))
bz = {"WEST": [], "SOUTH": [], "NORTH": [], "HOUSTON": []}
for r in li:
    if not isinstance(r, dict): continue
    z = (r.get("weatherZone") or r.get("zone") or "").upper().replace("LZ_", "")
    v = float(r.get("systemTotal") or r.get("loadForecast") or r.get("totalLoad") or 0)
    if z in bz and v > 0: bz[z].append(v)
load = {"west": mx(bz["WEST"]), "south": mx(bz["SOUTH"]), "north": mx(bz["NORTH"]), "houston": mx(bz["HOUSTON"])}
load["total"] = load["west"] + load["south"] + load["north"] + load["houston"]
si = shadow_data.get("_embedded", {}).get("dam_shadow_prices", shadow_data.get("data", []))
sc = {}
for r in si:
    if not isinstance(r, dict): continue
    nm = r.get("constraintName") or r.get("name") or "Unknown"
    sp = abs(float(r.get("shadowPrice") or 0))
    he = int(r.get("deliveryHour") or 0)
    if nm not in sc: sc[nm] = {"sps": [], "hrs": []}
    if sp > 0.01: sc[nm]["sps"].append(sp); sc[nm]["hrs"].append(he)
shadow_list = sorted([{"name": k, "maxSP": max(v["sps"]), "hours": sorted(set(v["hrs"])), "cnt": len(v["sps"])} for k, v in sc.items() if v["sps"]], key=lambda x: -x["maxSP"])[:15]
season = {1:"Winter",2:"Winter",3:"Spring",4:"Spring",5:"Spring",6:"Summer",7:"Summer",8:"Summer",9:"Fall",10:"Fall",11:"Fall",12:"Winter"}[NOW.month]
PB = [
    "TWINBU-HARGROVE 138KV [ACTIVE] Season:Summer+Winter PeakHE:HE5,6,4 Driver:West wind sub 5GW. Nodes:Russek(+31.7%),Hamilton(+6.8%)",
    "LARDVNTH-LASCRUCE 138KV [ACTIVE] Season:Summer PeakHE:HE20,21,22 Driver:South wind 2GW AND coastal 2GW. Nodes:Holcomb(+29.7%),Catarina(+17.9%),ValVerde(-7.9%)",
    "FORTMA-YELWJCKT 138KV [ACTIVE] Season:All PeakHE:HE21,20,23 Driver:West wind below 3GW overnight. Nodes:Junction(+50%),Russek(+3.2%)",
    "STP-ELMCREEK 345KV [ACTIVE] Season:Nov-Jan PeakHE:HE22,21,23 Driver:Low renewable overnight sub 8GW. Nodes:Catarina(+8%),Holcomb(+7.9%),Mainland(-9%)",
    "TREADWEL-YELWJCKT 138KV [ACTIVE] Season:Summer PeakHE:HE17,18,19 Driver:West load 9GW+. Nodes:Junction(+46.8%)",
    "LASCRUCE-MILO 138KV [ACTIVE] Season:Winter PeakHE:HE20,19,21 Driver:South AND coastal wind both 2GW+. Nodes:Holcomb(+28%),Catarina(+17.3%)",
    "WESTEX [ACTIVE] Season:All PeakHE:HE20,19,12 Driver:High renewable or west gen above 15GW overnight. Nodes:Diboll(+19.4%),Judkins(-71.8%),Russek(-66%)",
    "LNGSW-PRLSW 345KV [ACTIVE] Season:All PeakHE:HE1,2,24 Driver:West wind above 10GW overnight. Nodes:Judkins(+21.3%),Saddleback(+20.4%),Russek(+7%)",
    "E_PASP [ACTIVE] Season:All PeakHE:HE20,19,18 Driver:South load 18GW+ during down ramps. Nodes:Junction(+4%),ValVerde(-19.6%),Holcomb(-13.8%)",
    "NLARSW-PILONCIL 138KV [ACTIVE] Season:All PeakHE:HE24,1,2 Driver:Coastal wind 2.5GW+ or south wind 2.5GW+. Nodes:Catarina(+26%),FortDuncan(+12%)",
    "MGSW-CATSW 345KV [ACTIVE] Season:All PeakHE:HE23,19,20 Driver:West load 9GW+ with wind sub 8GW. Nodes:Judkins(+30%),Saddleback(+27%),Russek(+10%)",
    "LOBO-LARDVNTH 138KV [ACTIVE] Season:Feb-Mar PeakHE:HE22,19,21 Driver:South wind 2.5GW+ or coastal 2.8GW+. Nodes:Holcomb(+32.4%),Catarina(+21.8%)",
    "ESCONDID-GANSO 138KV [ACTIVE] Season:All PeakHE:HE8,9,1 Driver:West wind sub 3GW plus west load 9GW+. Nodes:Hamilton(+40.4%),FortDuncan(-26.1%)",
    "BCESW-SNDSW 345KV [ACTIVE] Season:Fall/Spring PeakHE:HE17,18,16 Driver:South wind sub 1GW south load 15GW+. Nodes:Holcomb(+11%),ValVerde(+11%)",
    "LNGSW-CONSW 345KV [ACTIVE] Season:Summer PeakHE:HE1,2,24 Driver:West wind 10GW+ west load 9GW+ overnight. Nodes:Judkins(+21.3%),Saddleback(+20%),Russek(+8%)",
    "YELWJCKT-FORTMA 138KV [ACTIVE] Season:Spring/Summer PeakHE:HE7,6,5 Driver:West winds 13GW+ offpeak 10GW+ onpeak. Nodes:Junction(-50%)",
    "ASHERTON-CATARINA 138KV [WATCH] Season:Summer PeakHE:HE13,12,14 Driver:Very low coastal AND south wind during solar window. Nodes:Catarina(+77%)",
    "MRVLY-ESTLD 69KV [WATCH] Season:Not seasonal PeakHE:HE20,19,21 Driver:North load above 15GW. Nodes:Cisco(+17.3%)",
    "STP-WAP 345KV [WATCH] Season:Summer PeakHE:HE17,16,13 Driver:Houston load 18GW+. Nodes:Mainland(+9.6%)",
    "PALOUSE-WOLFCAMP 138KV [WATCH] Season:All PeakHE:HE18,17,16 Driver:West load 9GW+ during solar ramp-down. Nodes:Russek(+30.6%)",
    "CRDCW-OLNEY 69KV [WATCH] Season:Spring/Summer PeakHE:HE17,18,16 Driver:North load 22GW+ DFW heat. Nodes:Olney(+78.7%)",
    "CARVER-TINSLEY 138KV [WATCH] Season:All PeakHE:HE21,20,22 Driver:West wind 10GW+ with coastal wind sub 2GW. Nodes:Hamilton(+32.3%),FortDuncan(+21%)",
    "MAXWELL-HAMILTON 138KV [WATCH] Season:Summer/Fall PeakHE:HE2,24,1 Driver:West wind 13GW+. Nodes:Hamilton(+23%),FortDuncan(+14.3%)",
    "MASN-KATEMCY 69KV [WATCH] Season:Winter PeakHE:HE19,18,23 Driver:Low west wind low north wind. Nodes:Junction(+25.1%)",
    "PRSLW-CONSW 345KV [WATCH] Season:Winter/Spring PeakHE:HE2,4,1 Driver:Mild temps lower loads west wind 8GW+. Nodes:Judkins(+29%),Saddleback(+23.4%)",
    "SONR-ATSO 69KV [WATCH] Season:All PeakHE:HE1,3,2 Driver:West load 9GW+ overnight. Nodes:Russek(+5%)",
]
PLAYBOOK = chr(10).join(PB)
sp_lines = []
for c in shadow_list:
    sp_lines.append("  " + c["name"] + ": max $" + str(int(c["maxSP"])) + "/MWh, HE " + ",".join(map(str, c["hours"][:3])))
sp_str = ("ERCOT DAM SHADOW PRICES:" + chr(10) + chr(10).join(sp_lines)) if sp_lines else ""
user_msg = ("Morning" if MODE == "morning" else "DA") + " briefing " + TODAY + " (" + season + ")" + chr(10)
user_msg += "West wind:" + str(round(wind["west"],1)) + "GW South:" + str(round(wind["south"],1)) + "GW Coastal:" + str(round(wind["coastal"],1)) + "GW Total:" + str(round(wind["total"],1)) + "GW Solar:" + str(round(wind["solar"],1)) + "GW" + chr(10)
user_msg += "West load:" + str(round(load["west"],1)) + "GW South:" + str(round(load["south"],1)) + "GW North:" + str(round(load["north"],1)) + "GW Houston:" + str(round(load["houston"],1)) + "GW Total:" + str(round(load["total"],1)) + "GW" + chr(10)
user_msg += sp_str + chr(10) + "Which constraints activate today?"
sys_msg = "You are HEN NOC Constraint Analyst. PLAYBOOK:" + chr(10) + PLAYBOOK
sys_msg += chr(10) + "RULES: ASCII only. No curly quotes. No em-dashes. No newlines in strings. No apostrophes."
sys_msg += chr(10) + "Return ONLY valid JSON: " + '{"summary":"text","riskLevel":"HIGH or MODERATE or LOW","highConfidence":[{"name":"x","priority":"ACTIVE or WATCH","likelyHours":"HE x","driver":"text","nodes":["x"],"season":"x","confidence":"HIGH or MEDIUM"}],"watchList":[{"name":"x","priority":"ACTIVE or WATCH","likelyHours":"HE x","driver":"text","nodes":["x"],"season":"x","confidence":"HIGH or MEDIUM"}],"unlikely":["x"],"operatorNote":"text"}'
print("Calling Claude...")
cr = requests.post("https://api.anthropic.com/v1/messages",
    headers={"Content-Type": "application/json", "x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01"},
    json={"model": "claude-sonnet-4-6", "max_tokens": 1500, "system": sys_msg, "messages": [{"role": "user", "content": user_msg}]},
    timeout=60)
raw = cr.json()["content"][0]["text"]
import re
clean = raw[raw.index("{"):raw.rindex("}")+1]
clean = re.sub(r'[\x00-\x1f\x7f]', ' ', clean)
result = json.loads(clean)
high = result.get("highConfidence", [])
watch_list = result.get("watchList", [])
unlikely = result.get("unlikely", [])
risk = result.get("riskLevel", "MODERATE")
rc = "#c0392b" if risk == "HIGH" else "#9a6200" if risk == "MODERATE" else "#1d6b3e"
Q = chr(39)
def chtml(c, col):
    sym = "🟢" if c.get("priority") == "ACTIVE" else "🟡"
    nodes = "".join(["<span style=" + Q + "font-size:10px;padding:2px 6px;border-radius:3px;background:rgba(75,172,198,0.1);color:#4BACC6;font-family:monospace;margin-right:4px" + Q + ">" + n + "</span>" for n in c.get("nodes", [])])
    out = "<div style=" + Q + "border-left:3px solid " + col + ";padding:12px 14px;margin-bottom:8px;background:#111f30;border-radius:0 6px 6px 0" + Q + ">"
    out += "<div style=" + Q + "display:flex;justify-content:space-between;margin-bottom:4px" + Q + "><strong style=" + Q + "font-size:13px;color:#e8f4f8" + Q + ">" + sym + " " + c.get("name","") + "</strong>"
    out += "<span style=" + Q + "font-size:10px;font-weight:700;padding:2px 8px;border-radius:3px;color:" + col + Q + ">" + c.get("confidence","") + "</span></div>"
    out += "<div style=" + Q + "font-size:11px;color:#7ea8bc;margin-bottom:4px" + Q + ">" + c.get("likelyHours","") + " - " + c.get("season","") + "</div>"
    out += "<div style=" + Q + "font-size:12px;color:#a0b8c8;margin-bottom:6px" + Q + ">" + c.get("driver","") + "</div>"
    out += "<div>" + nodes + "</div></div>"
    return out
def gcell(label, val, warn=False, alert=False):
    col = "#c0392b" if alert else "#9a6200" if warn else "#e8f4f8"
    bg = "rgba(224,82,82,0.07)" if alert else "rgba(212,135,42,0.07)" if warn else "#111f30"
    return "<div style=" + Q + "background:" + bg + ";border-radius:6px;padding:10px 12px" + Q + "><div style=" + Q + "font-size:9px;font-weight:600;text-transform:uppercase;letter-spacing:0.06em;color:#3d6478;margin-bottom:4px" + Q + ">" + label + "</div><div style=" + Q + "font-size:20px;font-weight:600;color:" + col + ";font-family:monospace" + Q + ">" + val + "</div></div>"
sp_tbl = ""
if shadow_list:
    rows = ""
    for c in shadow_list[:10]:
        sp_col = "#f28b82" if c["maxSP"] > 200 else "#f5c842" if c["maxSP"] > 50 else "#5db87a"
        rows += "<tr><td style=" + Q + "padding:6px 8px;font-size:11px;color:#e8f4f8;border-bottom:1px solid rgba(255,255,255,0.05)" + Q + ">" + c["name"] + "</td><td style=" + Q + "padding:6px 8px;font-size:12px;font-weight:600;color:" + sp_col + ";border-bottom:1px solid rgba(255,255,255,0.05)" + Q + ">$" + str(int(c["maxSP"])) + "</td><td style=" + Q + "padding:6px 8px;font-size:11px;color:#7ea8bc;border-bottom:1px solid rgba(255,255,255,0.05)" + Q + ">HE " + ",".join(map(str, c["hours"][:3])) + "</td></tr>"
    sp_tbl = "<div style=" + Q + "background:#0d1825;border:0.5px solid rgba(75,172,198,0.12);border-radius:10px;padding:1.25rem;margin-bottom:1rem" + Q + "><div style=" + Q + "font-size:11px;font-weight:600;text-transform:uppercase;color:#4BACC6;margin-bottom:10px" + Q + ">ERCOT DAM Shadow Prices</div><table style=" + Q + "width:100%;border-collapse:collapse" + Q + "><thead><tr><th>Constraint</th><th>Max SP</th><th>Peak hrs</th></tr></thead><tbody>" + rows + "</tbody></table></div>"
body = "<div style=" + Q + "background:#0d1825;border:0.5px solid rgba(75,172,198,0.12);border-radius:10px;padding:1.25rem;margin-bottom:1rem" + Q + ">"
body += "<div style=" + Q + "font-size:13px;color:#a0c8d8;line-height:1.5;margin-bottom:1rem" + Q + ">" + result.get("summary","") + "</div>"
body += "<div style=" + Q + "font-size:11px;font-weight:600;text-transform:uppercase;color:#4BACC6;margin-bottom:0.875rem" + Q + ">Wind generation forecast</div>"
body += "<div style=" + Q + "display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-bottom:1rem" + Q + ">"
body += gcell("West wind", str(round(wind["west"],1)) + " GW", wind["west"] < 5, wind["west"] < 2)
body += gcell("South wind", str(round(wind["south"],1)) + " GW", wind["south"] > 1.5, wind["south"] > 2.5)
body += gcell("Coastal wind", str(round(wind["coastal"],1)) + " GW", wind["coastal"] > 1.5, wind["coastal"] > 2.5)
body += gcell("Panhandle", str(round(wind["pan"],1)) + " GW")
body += gcell("Total wind", str(round(wind["total"],1)) + " GW", wind["total"] < 5 or wind["total"] > 12, wind["total"] < 2)
body += gcell("Solar", str(round(wind["solar"],1)) + " GW") + "</div>"
body += "<div style=" + Q + "font-size:11px;font-weight:600;text-transform:uppercase;color:#4BACC6;margin-bottom:0.875rem" + Q + ">Load forecast by zone</div>"
body += "<div style=" + Q + "display:grid;grid-template-columns:repeat(6,1fr);gap:8px" + Q + ">"
body += gcell("West zone", str(round(load["west"],1)) + " GW", load["west"] >= 8.5, load["west"] >= 9.5)
body += gcell("South zone", str(round(load["south"],1)) + " GW", load["south"] >= 16, load["south"] >= 18)
body += gcell("North zone", str(round(load["north"],1)) + " GW", load["north"] >= 20, load["north"] >= 22)
body += gcell("Houston zone", str(round(load["houston"],1)) + " GW", load["houston"] >= 16, load["houston"] >= 18)
body += gcell("ERCOT total", str(round(load["total"],1)) + " GW")
body += gcell("Generated", NOW.strftime("%H:%M CDT")) + "</div></div>"
body += sp_tbl
if high: body += "<div style=" + Q + "background:#0d1825;border:0.5px solid rgba(75,172,198,0.12);border-radius:10px;padding:1.25rem;margin-bottom:1rem" + Q + "><div style=" + Q + "font-size:11px;font-weight:600;text-transform:uppercase;color:#c0392b;margin-bottom:0.875rem" + Q + ">High-probability constraints</div>" + "".join([chtml(c, "#c0392b") for c in high]) + "</div>"
if watch_list: body += "<div style=" + Q + "background:#0d1825;border:0.5px solid rgba(75,172,198,0.12);border-radius:10px;padding:1.25rem;margin-bottom:1rem" + Q + "><div style=" + Q + "font-size:11px;font-weight:600;text-transform:uppercase;color:#4BACC6;margin-bottom:0.875rem" + Q + ">Watch list</div>" + "".join([chtml(c, "#4BACC6") for c in watch_list]) + "</div>"
if result.get("operatorNote"): body += "<div style=" + Q + "background:#0d1825;border:0.5px solid rgba(75,172,198,0.12);border-radius:10px;padding:1.25rem;margin-bottom:1rem" + Q + "><div style=" + Q + "font-size:11px;font-weight:600;text-transform:uppercase;color:#9a6200;margin-bottom:6px" + Q + ">Operator note</div><div style=" + Q + "font-size:12px;color:#c8b87a;padding:10px 12px;background:rgba(212,135,42,0.07);border-left:3px solid #9a6200" + Q + ">" + result["operatorNote"] + "</div></div>"
if unlikely: body += "<div style=" + Q + "background:#0a1220;border:0.5px solid rgba(75,172,198,0.08);border-radius:10px;padding:1rem" + Q + "><div style=" + Q + "font-size:10px;font-weight:600;text-transform:uppercase;color:#3d6478;margin-bottom:6px" + Q + ">Low probability today</div><div style=" + Q + "font-size:11px;color:#3d6478" + Q + ">" + " | ".join(unlikely) + "</div></div>"
html = "<!DOCTYPE html><html lang=" + Q + "en" + Q + "><head><meta charset=" + Q + "UTF-8" + Q + "><meta name=" + Q + "viewport" + Q + " content=" + Q + "width=device-width,initial-scale=1.0" + Q + "><title>HEN Briefing " + TODAY + "</title><style>*{box-sizing:border-box;margin:0;padding:0}body{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;background:#070f1a;color:#e8f4f8;min-height:100vh}</style></head><body>"
html += "<div style=" + Q + "background:#022a4e;border-bottom:1px solid rgba(75,172,198,0.25);padding:0 1.5rem;height:52px;display:flex;align-items:center;justify-content:space-between" + Q + "><strong>HEN Congestion Dashboard</strong>"
html += "<span style=" + Q + "font-size:11px;color:#4BACC6;background:rgba(75,172,198,0.1);border:1px solid rgba(75,172,198,0.25);padding:3px 10px;border-radius:4px" + Q + ">" + TODAY + " " + ("Morning" if MODE == "morning" else "DA 12:45+") + "</span>"
html += "<span style=" + Q + "font-size:10px;font-weight:700;padding:3px 9px;border-radius:4px;background:" + rc + ";color:white" + Q + ">" + risk + "</span></div>"
html += "<div style=" + Q + "max-width:900px;margin:0 auto;padding:1.5rem" + Q + ">" + body + "</div></body></html>"
with open("results.html", "w") as f: f.write(html)
print("Done. Mode:" + MODE + " Risk:" + risk + " High:" + str(len(high)) + " Watch:" + str(len(watch_list)))





