import requests
import os

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
TASK_DB_ID = os.getenv("TASK_DB_ID")
BTS_DB_ID = os.getenv("BTS_DB_ID")

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

def query_db(db_id):
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    res = requests.post(url, headers=headers)
    return res.json()["results"]

def update_task(task_id, bts_ids):
    url = f"https://api.notion.com/v1/pages/{task_id}"
    data = {
        "properties": {
            "Bug Tracking System": {   # ✅ Task DB 속성명 그대로
            "relation": [{"id": bts_id} for bts_id in matched_bts]
    }
}

            }
        }
    }
    requests.patch(url, headers=headers, json=data)

def main():
    tasks = query_db(TASK_DB_ID)
    bts_items = query_db(BTS_DB_ID)

    for task in tasks:
        task_ver = task["properties"]["Product Version"]["select"]["name"]
        task_id = task["id"]

        matched_bts = [
            bts["id"] for bts in bts_items
            if bts["properties"]["Product Version"]["select"]["name"] == task_ver
        ]

        if matched_bts:
            update_task(task_id, matched_bts)

if __name__ == "__main__":
    main()
