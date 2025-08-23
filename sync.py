import os, time, requests

# ---- Secrets (GitHub Actions env) ----
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
TASK_DB_ID   = os.getenv("TASK_DB_ID")
BTS_DB_ID    = os.getenv("BTS_DB_ID")

# 속성명 기본값 (다르면 Secrets로 TASK_VER_PROP/BTS_VER_PROP/TASK_REL_PROP 덮어쓰기 가능)
TASK_VER_PROP = os.getenv("TASK_VER_PROP", "Product Version")
BTS_VER_PROP  = os.getenv("BTS_VER_PROP",  "Product Version")
TASK_REL_PROP = os.getenv("TASK_REL_PROP", "Bug Tracking System")  # 폴백용

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}

# -------------------- 유틸 --------------------
def query_db_all(db_id):
    """DB 전체 조회 (페이지네이션)"""
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
    """select / multi_select / text(rich_text) / title / status 지원 → set[str]"""
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

# ---- 핵심: Task DB 스키마에서 BTS로 향하는 relation 속성 '이름'을 찾는다
_REL_PROP_NAME_CACHE = None
def detect_relation_prop_name():
    global _REL_PROP_NAME_CACHE
    if _REL_PROP_NAME_CACHE:
        return _REL_PROP_NAME_CACHE

    norm = lambda s: (s or "").replace("-", "").lower()
    target = norm(BTS_DB_ID)

    url = f"https://api.notion.com/v1/databases/{TASK_DB_ID}"
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    schema = r.json()

    for name, prop in schema.get("properties", {}).items():
        if prop.get("type") == "relation":
            rel = prop.get("relation", {})  # <-- 스키마에는 dict로 들어있음
            if norm(rel.get("database_id")) == target:
                _REL_PROP_NAME_CACHE = name
                print(f"[info] detected relation prop name: {name}")
                return name

    # 못 찾으면 폴백 (Secrets로 지정했거나 수동 이름 사용)
    print(f"[warn] relation to BTS DB not detected from schema; fallback to '{TASK_REL_PROP}'")
    _REL_PROP_NAME_CACHE = TASK_REL_PROP
    return _REL_PROP_NAME_CACHE

def update_task_relations(
