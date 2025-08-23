import os
import time
import requests

# --- Secrets from GitHub Actions env ---
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
TASK_DB_ID   = os.getenv("TASK_DB_ID")
BTS_DB_ID    = os.getenv("BTS_DB_ID")

# Optional override via secrets (keep defaults if not provided)
TASK_VER_PROP = os.getenv("TASK_VER_PROP", "Product Version")
BTS_VER_PROP  = os.getenv("BTS_VER_PROP",  "Product Version")
TASK_REL_PROP = os.getenv("TASK_REL_PROP", "Bug Tracking System")  # fallback only

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}

# ---------------- Utils ----------------
def query_db_all(db_id):
    """Fetch all pages in a DB (pagination)."""
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    results, payload = [], {}
    while True:
        r = requests.post(url, headers=HEADERS, json=payload)
        r.raise_for_status()
        data = r.json()
        results.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        payload = {"start_cursor": data["next_cursor"]}
        time.sleep(0.2)
    return results

def extract_versions(page, prop_name):
    """Return set[str] from select / multi_select / rich_text / title / status."""
    p = page["properties"].get(prop_name)
    if not p:
        return set()
    t = p.get("type")
    if t == "select" and p["select"]:
        return {p["select"]["name"].strip()}
    if t == "multi_select":
        return {opt["name"].strip() for opt in p["multi_select"]}
    if t in ("rich_text", "title"):
        txt = "".join([b.get("plain_text", "") for b in p[t]]).strip()
        return {txt} if txt else set()
    if t == "status" and p["status"]:
        return {p["status"]["name"].strip()}
    return set()

def get_title(page):
    for _, v in page["properties"].items():
        if v.get("type") == "title":
            return "".join([b.get("plain_text", "") for b in v["title"]]) or "(untitled)"
    return "(untitled)"

# ---- Detect relation prop NAME from DB schema (reliable even with emoji) ----
_REL_PROP_NAME_CACHE = None
def detect_relation_prop_name():
    global _REL_PROP_NAME_CACHE
    if _REL_PROP_NAME_CACHE:
        return _REL_PROP_NAME_CACHE

    def norm(s): return (s or "").replace("-", "").lower()
    target = norm(BTS_DB_ID)

    url = f"https://api.notion.com/v1/databases/{TASK_DB_ID}"
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    schema = r.json()

    for name, prop in schema.get("properties", {}).items():
        if prop.get("type") == "relation":
            rel = prop.get("relation", {})
            if norm(rel.get("database_id")) == target:
                _REL_PROP_NAME_CACHE = name
                print(f"[info] detected relation prop name: {name}")
                return name

    # Fallback to provided name (if auto-detect fails)
    print(f"[warn] relation to BTS DB not detected; fallback to '{TASK_REL_PROP}'")
    _REL_PROP_NAME_CACHE = TASK_REL_PROP
    return _REL_PROP_NAME_CACHE

def update_task_relations(task_id, bts_ids):
    """Replace Task's relation with the matched BTS ids."""
    rel_name = detect_relation_prop_name()
    ids = list(dict.fromkeys(bts_ids))[:200]  # dedup + safety cap
    url = f"https://api.notion.com/v1/pages/{task_id}"
    body = {"properties": {rel_name: {"relation": [{"id": i} for i in ids]}}}
    r = requests.patch(url, headers=HEADERS, json=body)
    if r.status_code >= 400:
        print("[error] update failed:", r.status_code, r.text)
    r.raise_for_status()

# ---------------- Main ----------------
def main():
    if not (NOTION_TOKEN and TASK_DB_ID and BTS_DB_ID):
        raise SystemExit("Missing NOTION_TOKEN/TASK_DB_ID/BTS_DB_ID")

    print("[info] querying databases...")
    tasks = query_db_all(TASK_DB_ID)
    bts_items = query_db_all(BTS_DB_ID)

    # index BTS by version
    bts_by_ver = {}
    for b in bts_items:
        for v in extract_versions(b, BTS_VER_PROP):
            if v:
                bts_by_ver.setdefault(v, []).append(b["id"])
    print(f"[info] BTS versions indexed: {len(bts_by_ver)}")

    updated = 0
    for t in tasks:
        title = get_title(t)
        vers = extract_versions(t, TASK_VER_PROP)
        if not vers:
            print(f"[skip] Task '{title}' has no version")
            continue

        matched = []
        for v in vers:
            matched.extend(bts_by_ver.get(v, []))

        print(f"[match] Task '{title}' vers={list(vers)} -> BTS matched={len(matched)}")
        update_task_relations(t["id"], matched)
        updated += 1

    pr
