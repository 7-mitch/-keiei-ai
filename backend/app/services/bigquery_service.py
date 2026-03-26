# backend/app/services/bigquery_service.py
from google.cloud import bigquery
from google.oauth2 import service_account
import os

class BigQueryService:
    def __init__(self):
        self.client = bigquery.Client(
            project=os.getenv("GCP_PROJECT_ID")
        )
        self.dataset_id = os.getenv("BQ_DATASET_ID", "keiei_ai_dw")

    def create_dataset(self):
        """データセット作成"""
        dataset_ref = self.client.dataset(self.dataset_id)
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = "asia-northeast1"  # 東京
        self.client.create_dataset(dataset, exists_ok=True)
        return dataset

    def insert_rows(self, table_id: str, rows: list[dict]):
        """データ挿入"""
        table_ref = f"{self.client.project}.{self.dataset_id}.{table_id}"
        errors = self.client.insert_rows_json(table_ref, rows)
        if errors:
            raise Exception(f"BigQuery insert error: {errors}")
        return True

    def query(self, sql: str) -> list[dict]:
        """クエリ実行"""
        query_job = self.client.query(sql)
        results = query_job.result()
        return [dict(row) for row in results]
