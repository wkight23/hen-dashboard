"""Pull recent ERCOT binding constraints (NP6-86-CD) and write live_constraints.json.
Needs env vars: ERCOT_USERNAME, ERCOT_PASSWORD, ERCOT_SUBSCRIPTION_KEY
"""
import os, json, datetime, requests

TOKEN_URL = ("https://ercotb2c.b2clogin.com/ercotb2c.onmicrosoft.com/"
             "B2C_1_PUBAPI-ROPC-FLOW/oauth2/v2.0/token")
CLIENT_ID = "fec253ea-0d06-4272-a5e6-b478baeecd70"
API = "https://api.ercot.com/api/public-reports/np6-86-cd/shdw_prices_bnd_trns_const"
KEY = os.environ["ERCOT_SUBSCRIPTION_KEY"]

tok = requests.post(TOKEN_URL, data={
    "username": os.environ["ERCOT_USERNAME"], "password": os.environ["ERCOT_PASSWORD"],
    "grant_type": "password", "scope": f"openid {CLIENT_ID} offline_access",
    "client_id": CLIENT_ID, "response_type": "id_token"}, timeout=30).json()["id_token"]
H = {"Authorization": f"Bearer {tok}", "Ocp-Apim-Subscription-Key": KEY}

# ERCOT timestamps are Central Prevailing Time
try:
    from zoneinfo import ZoneInfo
    now = datetime.datetime.now(ZoneInfo("America/Chicago")).replace(tzinfo=None)
except Exception:
    now = datetime.datetime.utcnow() - datetime.timedelta(hours=5)
frm = (now - datetime.timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S")
to = now.strftime("%Y-%m-%dT%H:%M:%S")

rows, page = [], 1
while True:
    r = requests.get(API, headers=H, timeout=60, params={
        "SCEDTimestampFrom": frm, "SCEDTimestampTo": to, "size": 5000, "page": page})
    r.raise_for_status()
    j = r.json()
    names = [f["name"] for f in j.get("fields", [])]
    for d in j.get("data", []):
        rows.append(dict(zip(names, d)) if isinstance(d, list) else d)
    meta = j.get("_meta", {})
    if page >= int(meta.get("totalPages", 1)): break
    page += 1

def g(d, *keys):
    low = {k.lower(): v for k, v in d.items()}
    for k in keys:
        if k.lower() in low: return low[k.lower()]
    return None

recs = []
for d in rows:
    recs.append({
        "ts": g(d, "SCEDTimestamp", "timestamp"),
        "name": g(d, "constraintName") or "",
        "contingency": g(d, "contingencyName") or "",
        "from": g(d, "fromStation") or "", "to": g(d, "toStation") or "",
        "kv": g(d, "fromStationkV", "kV"),
        "sp": float(g(d, "shadowPrice") or 0),
        "limit": g(d, "limit"), "flow": g(d, "value"),
    })

stamps = sorted({r["ts"] for r in recs if r["ts"]})
latest = stamps[-1] if stamps else None
recent = set(stamps[-12:])  # ~last hour of 5-min SCED intervals
groups = {}
for r in recs:
    if r["ts"] not in recent: continue
    k = (r["name"], r["contingency"], r["from"], r["to"])
    g_ = groups.setdefault(k, {**r, "intervals": 0, "maxSP": 0, "latestTs": None, "nowSP": 0})
    g_["intervals"] += 1
    g_["maxSP"] = max(g_["maxSP"], r["sp"])
    if g_["latestTs"] is None or r["ts"] > g_["latestTs"]:
        g_["latestTs"], g_["nowSP"], g_["limit"], g_["flow"] = r["ts"], r["sp"], r["limit"], r["flow"]

out = {
    "fetchedUTC": datetime.datetime.utcnow().isoformat() + "Z",
    "latestSCED": latest,
    "intervalsInWindow": len(recent),
    "constraints": [
        {"name": v["name"], "contingency": v["contingency"], "from": v["from"], "to": v["to"],
         "kv": v["kv"], "shadowPrice": v["nowSP"], "maxShadowPrice": v["maxSP"],
         "intervalsBinding": v["intervals"], "bindingNow": v["latestTs"] == latest,
         "limit": v["limit"], "flow": v["flow"]}
        for v in groups.values()],
}
out["constraints"].sort(key=lambda c: -c["shadowPrice"])
json.dump(out, open("live_constraints.json", "w"), indent=1)
print(f"{len(out['constraints'])} constraints, latest SCED {latest}")
