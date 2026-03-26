# backend/app/services/dwh_schema.py
from google.cloud import bigquery

TABLES = {
    "tickets": [
        bigquery.SchemaField("id",          "STRING",    mode="REQUIRED"),
        bigquery.SchemaField("source",      "STRING"),
        bigquery.SchemaField("subject",     "STRING"),
        bigquery.SchemaField("description", "STRING"),
        bigquery.SchemaField("status",      "STRING"),
        bigquery.SchemaField("created_at",  "TIMESTAMP"),
    ],
    "documents": [
        bigquery.SchemaField("id",          "STRING",    mode="REQUIRED"),
        bigquery.SchemaField("source",      "STRING"),
        bigquery.SchemaField("content",     "STRING"),
        bigquery.SchemaField("embedding_id","STRING"),
        bigquery.SchemaField("created_at",  "TIMESTAMP"),
    ],
    "customers": [
        bigquery.SchemaField("id",          "STRING",    mode="REQUIRED"),
        bigquery.SchemaField("source",      "STRING"),
        bigquery.SchemaField("name",        "STRING"),
        bigquery.SchemaField("email",       "STRING"),
        bigquery.SchemaField("created_at",  "TIMESTAMP"),
    ],
}

def initialize_tables(bq_service):
    """全テーブルを初期化"""
    bq_service.create_dataset()
    for table_id, schema in TABLES.items():
        table_ref = f"{bq_service.client.project}.{bq_service.dataset_id}.{table_id}"
        table     = bigquery.Table(table_ref, schema=schema)
        bq_service.client.create_table(table, exists_ok=True)
        print(f"テーブル作成: {table_id}")