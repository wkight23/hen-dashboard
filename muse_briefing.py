"""
muse_briefing.py

Pulls live constraint flow + line rating data from the MUSE API (api1.marginalunit.com)
and matches it against HEN's shift-factor workbook (Congestion_Proj_heatmap.xlsx) to
produce a "how loaded is the line, right now" view for each of the 32 battery sites.

Output: muse_data.json - consumed by rt_briefing.py to render a Live Line Loading section.

Required env vars (GitHub Actions secrets):
    MUSE_USERNAME
    MUSE_PASSWORD
"""
import os, re, json, requests, pandas as pd
from datetime import datetime, timezone
from io import StringIO

MUSE_ROOT = "https://api1.marginalunit.com/muse/api"
MUSE_USERNAME = os.environ.get("MUSE_USERNAME", "")
MUSE_PASSWORD = os.environ.get("MUSE_PASSWORD", "")

# Same 32-site name mapping used in rt_briefing.py (workbook display name -> site code)
SF_TO_SP = {'Russek':'RUSSEKST_RN','Catarina':'CATARINA_B1','Holcomb':'HOLCOMB_RN1','Hamilton':'HAMI_BESS_RN',
    'FortDuncan':'FTDUNCAN_RN','Junction':'JUNCTION_RN','Judkins':'JDKNS_RN','Saddleback':'SADLBACK_RN',
    'Cedarvale':'CEDRVALE_RN','Toyah':'TOYAH_RN','Coyote':'COYOTSPR_RN','Faulkner':'FAULKNER_RN',
    'GardenCity':'GRDNE_ESR_RN','Gomez':'GOMZ_RN','Lonestar':'LONESTAR_RN','Rattlesnake':'RTLSNAKE_BT',
    'Sandlake':'SANDLAKE_RN','Screwbean':'SBEAN_BESS','ValVerde':'MV_VALV4_RN','Falfurrias':'FALFUR_RN',
    'Pavlov':'PAVLOV_BT_RN','Poteets':'POTEETS_RN','Tynan':'TYNAN_RN','WeilTract':'WLTC_ESR_RN',
    'Mainland':'MAINLAND_RN','Cisco':'CISC_RN','Diboll':'DIBOL_RN','Farmersville':'FRMRSVLW_RN',
    'LufkinSouth':'LFSTH_RN','MineralWells':'MNWL_BESS_RN','Olney':'OLNEYTN_RN','Pauline':'PAULN_RN'}
SITE_NAMES = {"RUSSEKST_RN":"Russek","JUNCTION_RN":"Junction","OLNEYTN_RN":"Olney","GRDNE_ESR_RN":"Garden City",
    "JDKNS_RN":"Judkins","LONESTAR_RN":"Lonestar","RTLSNAKE_BT":"Rattlesnake","SANDLAKE_RN":"Sandlake",
    "CEDRVALE_RN":"Cedarvale","COYOTSPR_RN":"Coyote","FAULKNER_RN":"Faulkner","SADLBACK_RN":"Saddleback",
    "TOYAH_RN":"Toyah","GOMZ_RN":"Gomez","SBEAN_BESS":"Screwbean","HAMI_BESS_RN":"Hamilton",
    "FTDUNCAN_RN":"Fort Duncan","CATARINA_B1":"Catarina","HOLCOMB_RN1":"Holcomb","POTEETS_RN":"Poteets",
    "FALFUR_RN":"Falfurrias","MV_VALV4_RN":"Val Verde","TYNAN_RN":"Tynan","WLTC_ESR_RN":"Weil Tract",
    "PAVLOV_BT_RN":"Pavlov","MAINLAND_RN":"Mainland","DIBOL_RN":"Diboll","PAULN_RN":"Pauline",
    "FRMRSVLW_RN":"Farmersville","MNWL_BESS_RN":"Mineral Wells","CISC_RN":"Cisco","LFSTH_RN":"Lufkin South"}

SF_MIN_THRESHOLD = 0.02  # ignore trivial (<2%) shift-factor exposure when tying a constraint to a site


def load_constraint_site_map(path="Congestion_Proj_heatmap.xlsx"):
    """Read the shift-factor workbook. Returns list of dicts:
    {name, sites: {display_name: shift_factor}}"""
    out = []
    try:
        df = pd.read_excel(path, header=None)
        site_order = list(SF_TO_SP.keys())  # matches workbook column order (cols 30-61, 0-indexed)
        for i in range(1, len(df)):
            name = df.iat[i, 0]
            if pd.isna(name) or str(name).strip().lower() == "new lines":
                continue
            name = str(name).strip()
            sites = {}
            for j, site in enumerate(site_order):
                try:
                    val = float(df.iat[i, 30 + j])
                    if abs(val) >= SF_MIN_THRESHOLD:
                        sites[site] = val
                except Exception:
                    continue
            out.append({"name": name, "sites": sites})
        print(f"Loaded {len(out)} constraints from shift-factor workbook")
    except FileNotFoundError:
        print(f"No shift factor workbook found at {path}")
    except Exception as e:
        print(f"Could not load shift factor workbook: {e}")
    return out


def parse_sf_name(name):
    """'TWINBU-HARGROVE 138KV HARGRO_TWINBU1_1' -> ('TWINBU','HARGROVE','138')"""
    m = re.match(r'^([A-Z0-9_]+)-([A-Z0-9_]+)\s+(\d+)KV', name)
    if m:
        return m.group(1), m.group(2), m.group(3)
    return None


def parse_muse_label(label):
    """'ORANS 69KV - ORN 69KV (100018_1_) FLO SBRTGRM8' -> ('ORANS','ORN','69')"""
    m = re.match(r'^([A-Z0-9_]+)\s+(\d+)KV\s+-\s+([A-Z0-9_]+)\s+(\d+)KV', label)
    if m:
        return m.group(1), m.group(3), m.group(2)
    return None


def fetch_muse_constraints(iso="ercot"):
    if not MUSE_USERNAME or not MUSE_PASSWORD:
        print("MUSE_USERNAME / MUSE_PASSWORD not set - skipping MUSE pull")
        return None
    url = f"{MUSE_ROOT}/{iso}/constraint_flows.csv"
    try:
        resp = requests.get(url, auth=(MUSE_USERNAME, MUSE_PASSWORD), timeout=60)
        if not resp.ok:
            print(f"MUSE API error: HTTP {resp.status_code}: {resp.text[:300]}")
            return None
        df = pd.read_csv(StringIO(resp.text))
        print(f"MUSE pull OK: {len(df)} constraint rows for {iso}")
        return df
    except Exception as e:
        print(f"MUSE API request failed: {e}")
        return None


def build_muse_lookup(muse_df):
    """(frozenset({sub1,sub2}), kv) -> list of row dicts"""
    lookup = {}
    unparsed = 0
    for _, row in muse_df.iterrows():
        p = parse_muse_label(str(row["label"]))
        if not p:
            unparsed += 1
            continue
        a, b, kv = p
        key = (frozenset([a, b]), kv)
        lookup.setdefault(key, []).append(row)
    print(f"MUSE label parse: {len(muse_df) - unparsed}/{len(muse_df)} parsed")
    return lookup


def match_and_score(sf_constraints, muse_lookup):
    """Returns list of matched constraint dicts with live loading data."""
    matched = []
    for c in sf_constraints:
        if not c["sites"]:
            continue  # not tied to any of our 32 sites, skip
        p = parse_sf_name(c["name"])
        if not p:
            continue
        a, b, kv = p
        key = (frozenset([a, b]), kv)
        rows = muse_lookup.get(key)
        if not rows:
            continue
        # A monitored branch can have multiple contingencies (sibling constraints);
        # take the one with the highest current loading, since that's the binding risk.
        best = None
        best_pct = -1
        for row in rows:
            try:
                rating = float(row["rating"])
                flow = float(row["constraint_flow"])
                if rating <= 0:
                    continue
                pct = abs(flow) / rating * 100
            except Exception:
                continue
            if pct > best_pct:
                best_pct = pct
                best = row
        if best is None:
            continue
        matched.append({
            "name": c["name"],
            "muse_label": str(best["label"]),
            "rating_mw": round(float(best["rating"]), 1),
            "flow_mw": round(float(best["constraint_flow"]), 1),
            "pct_loaded": round(best_pct, 1),
            "sites": {SITE_NAMES.get(SF_TO_SP.get(s), s): v for s, v in c["sites"].items()},
        })
    matched.sort(key=lambda x: -x["pct_loaded"])
    return matched


def build_by_site(matched, top_n=5):
    by_site = {}
    for c in matched:
        for site in c["sites"]:
            by_site.setdefault(site, []).append(c)
    for site in by_site:
        by_site[site].sort(key=lambda x: -x["pct_loaded"])
        by_site[site] = by_site[site][:top_n]
    return by_site


def loading_status(pct):
    if pct >= 97:
        return "CRITICAL"
    if pct >= 85:
        return "ELEVATED"
    return "NORMAL"


def main():
    sf_constraints = load_constraint_site_map()
    muse_df = fetch_muse_constraints("ercot")

    if muse_df is None:
        out = {"updated": datetime.now(timezone.utc).isoformat(), "available": False,
                "reason": "MUSE API unavailable this run", "top_constraints": [], "by_site": {}}
    else:
        muse_lookup = build_muse_lookup(muse_df)
        matched = match_and_score(sf_constraints, muse_lookup)
        by_site = build_by_site(matched)
        for c in matched:
            c["status"] = loading_status(c["pct_loaded"])
        for site, rows in by_site.items():
            for c in rows:
                c["status"] = loading_status(c["pct_loaded"])
        out = {
            "updated": datetime.now(timezone.utc).isoformat(),
            "available": True,
            "matched_count": len(matched),
            "tracked_count": len([c for c in sf_constraints if c["sites"]]),
            "top_constraints": matched[:15],
            "by_site": by_site,
        }
        print(f"Matched {len(matched)} live-loaded constraints tied to HEN sites")

    with open("muse_data.json", "w") as f:
        json.dump(out, f, indent=2)
    print("Wrote muse_data.json")


if __name__ == "__main__":
    main()
