# backend/app/services/data_collector.py
import os
import httpx
from datetime import datetime
from app.services.bigquery_service import BigQueryService

class ZendeskCollector:
    def __init__(self):
        self.base_url = os.getenv("ZENDESK_BASE_URL")
        self.email    = os.getenv("ZENDESK_EMAIL")
        self.token    = os.getenv("ZENDESK_API_TOKEN")

    async def fetch_tickets(self) -> list[dict]:
        auth = (f"{self.email}/token", self.token)
        async with httpx.AsyncClient() as client:
            res = await client.get(
                f"{self.base_url}/api/v2/tickets.json",
                auth=auth
            )
            res.raise_for_status()
            tickets = res.json().get("tickets", [])

        return [
            {
                "id":          str(t["id"]),
                "source":      "zendesk",
                "subject":     t.get("subject", ""),
                "description": t.get("description", ""),
                "status":      t.get("status", ""),
                "created_at":  t.get("created_at", ""),
            }
            for t in tickets
        ]

class KintoneCollector:
    def __init__(self):
        self.base_url = os.getenv("KINTONE_BASE_URL")
        self.token    = os.getenv("KINTONE_API_TOKEN")
        self.app_id   = os.getenv("KINTONE_APP_ID")

    async def fetch_records(self) -> list[dict]:
        headers = {"X-Cybozu-API-Token": self.token}
        async with httpx.AsyncClient() as client:
            res = await client.get(
                f"{self.base_url}/k/v1/records.json",
                headers=headers,
                params={"app": self.app_id}
            )
            res.raise_for_status()
            records = res.json().get("records", [])

        return [
            {
                "id":      r.get("$id", {}).get("value", ""),
                "source":  "kintone",
                "content": str(r),
                "created_at": datetime.utcnow().isoformat(),
            }
            for r in records
        ]

async def collect_and_store():
    """全データソースから収集してBigQueryに保存"""
    bq = BigQueryService()

    # Zendesk
    try:
        zendesk   = ZendeskCollector()
        tickets   = await zendesk.fetch_tickets()
        if tickets:
            bq.insert_rows("tickets", tickets)
            print(f"Zendesk: {len(tickets)}件 保存完了")
    except Exception as e:
        print(f"Zendesk収集エラー: {e}")

    # kintone
    try:
        kintone = KintoneCollector()
        records = await kintone.fetch_records()
        if records:
            bq.insert_rows("documents", records)
            print(f"kintone: {len(records)}件 保存完了")
    except Exception as e:
        print(f"kintone収集エラー: {e}")
