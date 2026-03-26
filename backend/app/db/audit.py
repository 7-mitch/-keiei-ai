import json
from app.db.connection import get_conn

async def record_audit(
    operator_id:    int | None,
    operator_type:  str,
    target_type:    str,
    target_id:      int,
    action:         str,
    before_value:   dict | None = None,
    after_value:    dict | None = None,
    reason:         str | None  = None,
    ai_confidence:  float | None = None,
    session_id:     str | None  = None,
    ip_address:     str | None  = None,
) -> None:
    async with get_conn() as conn:
        await conn.execute("""
            INSERT INTO audit_logs (
                operator_id, operator_type,
                target_type, target_id, action,
                before_value, after_value,
                reason, ai_confidence,
                session_id, ip_address
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
        """,
            operator_id, operator_type,
            target_type, target_id, action,
            json.dumps(before_value) if before_value else None,
            json.dumps(after_value)  if after_value  else None,
            reason, ai_confidence,
            session_id, ip_address,
        )
