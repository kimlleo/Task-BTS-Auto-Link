import os, time, requests

# ---- Secrets (GitHub Actions에서 env로 주입) ----
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
TASK_DB_ID   = os.getenv("TASK_DB_ID")
BTS_DB_ID    = os.getenv("BTS_DB_ID")

# 버전/관계 속성 이름(기본값). 이름을 쓰지 않고 자동탐지하므로 그대로 둬도 됨.
TASK_VER_PROP = os.getenv("TASK_VER_PROP", "Product Version")
BTS_VER_PROP  = os.getenv("BTS_VER_PROP",  "Product Version")
TASK_REL_PROP = os.getenv("TASK_REL_PROP", "Bug Tracking System")

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}

def query_db_all(db_id):
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    results, payload = [], {}
    while True:
        r = requests.post(url, headers=HEADERS, json=payload)
        r.raise_for_status()
        data = r.json()
        results.extend(data.get("results", []))
        if not data.get("has_more"): break
        payload = {"start_cursor": data["next_cursor"]}
        time.sleep(0.2)
    return results

def extract_versions(page, prop_name):
    p = page["properties"].get(prop_name)
    if not p: return set()
    t = p.get("type")
    if t == "select" and p["select"]:
        return {p["select"]["name"].strip()}
    if t == "multi_select":
        return {o["name"].strip() for o in p["multi_select"]}
    if t in ("rich_text","title"):
        txt = "".join([b.get("plain_text","") for b in p[t]]).strip()
        return {txt} if txt else set()
    if t == "status" and p["status"]:
        return {p["status"]["name"].strip()}
    return set()

def get_title(page):
    for _, v in page["properties"].items():
        if v.get("type") == "title":
            return "".join([b.get("plain_text","") for b in v["title"]]) or "(untitled)"
    return "(untitled)"

def find_rel_prop_key_for_bts(page):
    """
    이 페이지의 속성들 중에서 'relation' 이고 relation.database_id가 BTS_DB_ID 인 속성을 찾아
    그 속성의 'id'를 반환. (이름/이모지 무시)
    못 찾으면 TASK_REL_PROP(이름 키)로 폴백.
    """
    norm = lambda s: (s or "").replace("-", "").lower()
    target = norm(BTS_DB_ID)
    for name, prop in page["properties"].items():
        if prop.get("type") == "relation":
            rel = prop.get("relation", {})
            dbid = rel.get("database_id")
            if norm(dbid) == target:
                return prop["id"]  # property ID로 업데이트
    # 폴백: 이름으로 시도 (시크릿에 정확한 이름 넣었을 때 대비)
    return TASK_REL_PROP

def update_task_relations(task_page, bts_ids):
    ids = list(dict.fromkeys(bts_ids))[:200]
    prop_key = find_rel_prop_key_for_bts(task_page)
    url = f"https://api.notion.com/v1/pages/{task_page['id']}"
    body = {"properties": {prop_key: {"relation": [{"id": i} for i in ids]}}}
    r = requests.patch(url, headers=HEADERS, json=body)
    if r.status_code >= 400:
        print("[error] update failed:", r.status_code, r.text)
    r.raise_for_status()

def main():
    if not (NOTION_TOKEN and TASK_DB_ID and BTS_DB_ID):
        raise SystemExit("Missing NOTION_TOKEN/TASK_DB_ID/BTS_DB_ID")

    print("[info] querying databases...")
    tasks = query_db_all(TASK_DB_ID)
    bts_items = query_db_all(BTS_DB_ID)

    # BTS: version → [page_id...]
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

        update_task_relations(t, matched)
        updated += 1

    print(f"[done] tasks processed={updated}")

if __name__ == "__main__":
    main()
