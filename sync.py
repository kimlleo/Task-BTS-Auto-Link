import os, time, requests

# ---- 환경변수(Secrets) ----
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
TASK_DB_ID   = os.getenv("TASK_DB_ID")
BTS_DB_ID    = os.getenv("BTS_DB_ID")

# 속성 이름(다르면 여기만 바꾸세요)
TASK_VER_PROP = os.getenv("TASK_VER_PROP", "Product Version")      # Task DB의 버전 속성명
BTS_VER_PROP  = os.getenv("BTS_VER_PROP",  "Product Version")      # BTS DB의 버전 속성명
TASK_REL_PROP = os.getenv("TASK_REL_PROP", "Bug Tracking System")  # Task DB의 Relation 속성명

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}

# ---------- 유틸 ----------
def query_db_all(db_id):
    """데이터베이스 전체 조회(페이지네이션 처리)."""
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
        time.sleep(0.2)  # rate limit 여유
    return results

def extract_versions(page, prop_name):
    """select / multi_select / text(rich_text) 모두 지원 → set[str] 반환."""
    p = page["properties"].get(prop_name)
    if not p:
        return set()
    t = p.get("type")
    if t == "select" and p["select"]:
        return {p["select"]["name"]}
    if t == "multi_select":
        return {opt["name"] for opt in p["multi_select"]}
    if t in ("rich_text", "title"):
        # 텍스트 속성/제목에서 plain_text 추출
        txt = "".join([b.get("p]()
