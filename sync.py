import os, time, requests

# ---- Secrets (GitHub Actions에서 env로 주입) ----
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
TASK_DB_ID   = os.getenv("TASK_DB_ID")
BTS_DB_ID    = os.getenv("BTS_DB_ID")

# 속성명 (Secrets로 덮어쓸 수 있음)
TASK_VER_PROP = os.getenv("TASK_VER_PROP", "Product Version")
BTS_VER_PROP  = os.getenv("BTS_VER_PROP",  "Product Version")
TASK_REL_PROP = os.getenv("TASK_REL_PROP", "Bug Tracking System")

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}

def query_db_all(db_id):
    """DB 전체 조회 (페이지네이션 처리)"""
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    results, payload = [], {}
    while True:
        res = requests.post(url, headers=HEADERS, json=payload)
        res.raise_for_status()
        data = res.json()
        results.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        payload = {"start_cursor": data["next_cursor"]}
        time.sleep(0.2)
    return results

def extract_versions(page, prop_name):
    """select / multi_select / text(rich_text) / title / status 지원 → set[str]"""
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

def update_task_relations(task_id, bts_ids):
    """Task의 Relation을 매칭 결과로 치환"""
    ids = list(dict.fromkeys(bts_ids))[:200]
    url = f"https://api.notion.com/v1/pages/{task_id}"
    body = {"properties": {TASK_REL_PROP: {"relation": [{"id": i} for i in ids]}}}
    res = requests.patch(url, headers=HEADERS, json=body)
    if res.status_code >= 400:
        print("[error] update failed:", res.status_code, res.text)
    res.raise_for_status()

def get_title(page):
    for k, v in page["properties"].items():
        if v.get("type") == "title":
            return "".join([b.get("plain_text", "") for b in v["title"]]) or "(untitled)"
    return "(untitled)"

def main():
    if not (NOTION_TOKEN and TASK_DB_ID and BTS_DB_ID):
        raise SystemExit("Missing NOTION_TOKEN/TASK_DB_ID/BTS_DB_ID")

    print("[info] querying databases...")
    tasks = query_db_all(TASK_DB_ID)
    bts_items = query_db_all(BTS_DB_ID)

    # BTS 인덱스: version → [page_id...]
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

    print(f"[done] tasks processed={updated}")

if __name__ == "__main__":
    main()
