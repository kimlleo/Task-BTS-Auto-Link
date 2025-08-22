import requests
import os

NOTION_TOKEN = os.getenv("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")
TASK_DB_ID = os.getenv("154ba496d7b880fba791c4cc9a94a13e")
BTS_DB_ID = os.getenv("278e3be079ca4c9d98b409884b73fe6e")

headers = {
    "Authorization": f"Bearer {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}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

def query_db(db_id):
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    res = requests.post(url, headers=headers)
    res.raise_for_status()
    return res.json()["results"]

def update_task(task_id, bts_ids):
    url = f"https://api.notion.com/v1/pages/{task_id}"
    data = {
        "properties": {
            "Bug Tracking System": {   # ✅ Task DB Relation 속성 이름 그대로
                "relation": [{"id": bts_id} for bts_id in bts_ids]
            }
        }
    }
    res = requests.patch(url, headers=headers, json=data)
    res.raise_for_status()

def main():
    tasks = query_db(TASK_DB_ID)
    bts_items = query_db(BTS_DB_ID)

    for task in tasks:
        task_props = task["properties"]
        if "Product Version" not in task_props or not task_props["Product Version"]["select"]:
            continue
        task_ver = task_props["Product Version"]["select"]["name"]
        task_id = task["id"]

        matched_bts = []
        for bts in bts_items:
            bts_props = bts["properties"]
            if "Product Version" in bts_props and bts_props["Product Version"]["select"]:
                bts_ver = bts_props["Product Version"]["select"]["name"]
                if bts_ver == task_ver:
                    matched_bts.append(bts["id"])

        if matched_bts:
            update_task(task_id, matched_bts)

if __name__ == "__main__":
    main()
