#!/usr/bin/env python3
import json, time, os
import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

API_BASE = "https://bloxfruitsvalues.com"
# connect timeout, read timeout
TIMEOUT = (5, 30)
LIMIT = 100  # you can raise later after it works consistently

COOKIES = {
    # rotate this when it expires
    "cf_clearance": "uy2i3IT1DRNfuV_c0MDyx9tw_Exp2mtXadcjmaOdbbk-1762877691-1.2.1.1-0MjSVssmxtCJVfKeaw.H9NGwGq3RTMleWOumFLEB6xAUX5_0EUZCREXEcQpNsSqvwYuGgRiktYblGcKG2RtQOWNRXjQnXb22cs7EqRUSY7ZJNS.d0FJHGwpvnVaZ6jiuEZycFMp1Nmac1kkqOc91kkkJieBZzepWlusy1mh7_dp31B8MDauj.7JpSigeoZpABLEoZibhxwavraR8SoGMfXZvspq0_hUhra2r_mImsgk",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/123 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://bloxfruitsvalues.com/values",
    "Origin": "https://bloxfruitsvalues.com",
}

GROUPS = {
    "fruits":   {"group": "Bloxfruits", "rarities": ["Mythical","Legendary","Epic","Rare","Uncommon","Common"]},
    "limiteds": {"group": "Limiteds",   "rarities": ["Mythical","Legendary","Epic","Rare","Uncommon","Common"]},
    "gamepasses": {"group": "Gamepasses","rarities": ["Mythical","Legendary","Epic","Rare","Uncommon","Common"]},
}

def make_session():
    s = requests.Session()
    retry = Retry(
        total=5,
        connect=3,
        read=3,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.headers.update(HEADERS)
    s.cookies.update(COOKIES)
    return s

def get_json(session, url, params=None):
    try:
        r = session.get(url, params=params or {}, timeout=TIMEOUT)
        if r.status_code != 200:
            snippet = (r.text or "")[:140].replace("\n", " ")
            print("[warn]", url, "->", r.status_code, snippet)
            return None
        try:
            return r.json()
        except Exception as e:
            print(f"[warn] JSON parse failed for {url}: {e}")
            return None
    except requests.exceptions.ReadTimeout:
        print("[warn] read timeout:", url)
        return None
    except requests.exceptions.RequestException as e:
        print("[warn] request error:", url, e)
        return None

def fetch_group_rarity(session, group, rarity, limit=LIMIT):
    url = f"{API_BASE}/api/v1/items/{group}/{rarity}"
    page = 1
    out = []
    while True:
        data = get_json(session, url, params={"limit": limit, "page": page})
        if not data:
            break

        items = data
        pagination = {}
        if isinstance(data, dict):
            items_field = data.get("items")
            pagination = data.get("pagination")
            if isinstance(items_field, dict):
                items = items_field.get("items") or items_field.get("docs")
                pagination = pagination or items_field.get("pagination") or {}
            else:
                items = items_field
                pagination = pagination or {}

        if not isinstance(items, list) or not items:
            break
        out.extend(items)

        pg = pagination if isinstance(pagination, dict) else {}
        has_more = bool(pg.get("hasMore")) or (pg.get("page", 1) < pg.get("totalPages", 1))
        if not has_more:
            break
        page += 1
        time.sleep(0.25)  # gentle pacing
    return out

def norm_item(x):
    name = (x.get("name") or x.get("title") or "").strip()
    if not name:
        return None
    def maybe_int(v):
        try: return int(v)
        except: return None
    value = (maybe_int(x.get("value")) or maybe_int(x.get("pvalue"))
             or maybe_int(x.get("maxValue")) or maybe_int(x.get("minValue")) or 0)
    return {
        "name": name,
        "value": value or 0,
        "rarity": x.get("rarity") or x.get("tier"),
        "demand": x.get("demand") or x.get("demandScore") or x.get("popularity"),
        "category": x.get("category") or x.get("type") or x.get("group"),
    }

def main():
    s = make_session()
    all_data = {"fruits": [], "limiteds": [], "gamepasses": [], "all": []}

    for bucket, cfg in GROUPS.items():
        g = cfg["group"]
        total = 0
        for r in cfg["rarities"]:
            raw = fetch_group_rarity(s, g, r)
            count = len(raw)
            print(f"[info] {g}/{r}: {count} items")
            for it in raw:
                ni = norm_item(it)
                if ni: all_data[bucket].append(ni)
            total += count
            time.sleep(0.25)
        print(f"[sum] {bucket}: {total}")

    all_data["all"] = all_data["fruits"] + all_data["limiteds"] + all_data["gamepasses"]
    with open("blox_values.json", "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)
    print("[done] wrote blox_values.json")
    print({k: len(v) for k, v in all_data.items() if isinstance(v, list) and k != "all"})

if __name__ == "__main__":
    main()
