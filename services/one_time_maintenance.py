"""One-off, bounded PostgreSQL/SQLite maintenance for the v4.3.28 deployment.

Only the *three* pre-existing error-log rows may be removed, and only on the first
successful maintenance transaction. No recurring cleanup, no arbitrary last-N
selection, and no changes to functional tests, QR scans, or student activity.
The marker deliberately lives outside application backup/restore tables, so a
backup restored through the app cannot re-arm the cleanup.
"""

import json
from sqlalchemy import text


ONE_TIME_ERROR_CLEANUP_KEY = "error_logs_exactly_three_once_v4328"


def cleanup_initial_three_error_logs_once(engine):
    """Run once at deployment, transactionally, under a durable database marker.

    If the error_logs table contains other than EXACTLY three rows, skip the
    deletion permanently. A mismatch must never be 'fixed' by deleting the
    newest/oldest three entries, because the original records cannot be
    identified without their IDs. Repeated startups are read-only.

    Returns dict with result ('deleted', 'skipped', 'already_processed'), count
    and the selected IDs (when deleted). Identifiers are stored for diagnostics
    but error text and personal data are not copied to the marker.
    """
    with engine.begin() as conn:
        # Gunicorn may start several workers. Serialize the one-time operation
        # between PostgreSQL workers on this database, until commit/rollback.
        if conn.dialect.name == "postgresql":
            conn.execute(text("SELECT pg_advisory_xact_lock(432800031)"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS app_one_time_maintenance (
                key VARCHAR(100) PRIMARY KEY,
                result TEXT NOT NULL,
                executed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        previous = conn.execute(
            text("SELECT result FROM app_one_time_maintenance WHERE key = :key"),
            {"key": ONE_TIME_ERROR_CLEANUP_KEY},
        ).scalar_one_or_none()
        if previous is not None:
            result = json.loads(previous)
            return {**result, "status": "already_processed"}

        count = int(conn.execute(text("SELECT COUNT(*) FROM error_logs")).scalar_one())
        if count == 3:
            ids = [int(row[0]) for row in conn.execute(
                text("SELECT id FROM error_logs ORDER BY id LIMIT 3")
            ).all()]
            if len(ids) != 3:
                raise RuntimeError("Error-log count changed while selecting cleanup rows")
            deleted = conn.execute(
                text("DELETE FROM error_logs WHERE id IN (:id1, :id2, :id3)"),
                {"id1": ids[0], "id2": ids[1], "id3": ids[2]},
            )
            if deleted.rowcount != 3:
                # Roll back everything, including the marker; no partial deletion.
                raise RuntimeError("Unexpected number of error-log rows removed")
            result = {"status": "deleted", "found": 3, "deleted": 3, "ids": ids}
        else:
            # Consume the one-time opportunity even if no errors exist or
            # extra records have appeared. Never run on future log entries.
            result = {"status": "skipped", "found": count, "deleted": 0,
                      "reason": "initial_error_count_is_not_three"}

        conn.execute(text("""
            INSERT INTO app_one_time_maintenance (key, result)
            VALUES (:key, :result)
        """), {"key": ONE_TIME_ERROR_CLEANUP_KEY,
                "result": json.dumps(result, ensure_ascii=False)})
        return result


# Đây là thao tác mở kỳ thực nghiệm chính thức, KHÔNG phải công cụ
# làm sai lệch kết quả kiểm thử. Lỗi trước kỳ được lưu nguyên trạng
# dưới dạng bản lưu bất biến; các lỗi mới vẫn được ghi và hiển thị.
LEGACY_ERROR_ARCHIVE_KEY = "pre_experiment_error_log_archive_20261125"


def archive_pre_experiment_error_logs_once(engine):
    """Chuyển nhật ký lỗi CŨ sang kho lưu riêng trong một giao dịch duy nhất.

    - Ghi lại đầy đủ nội dung bản gốc, thời điểm, ID để kiểm toán/khôi phục.
    - Xóa khỏi bảng nhật ký đang hiển thị đúng các ID vừa được sao lưu.
    - Không đụng FunctionalTestRun, OAuth, QR, môn học, lớp, sinh viên.
    - Marker bảo đảm KHÔNG bao giờ tự động xóa các lỗi mới.
    """
    from sqlalchemy import bindparam
    with engine.begin() as conn:
        if conn.dialect.name == "postgresql":
            conn.execute(text("SELECT pg_advisory_xact_lock(2026112501)"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS app_one_time_maintenance (
                key VARCHAR(100) PRIMARY KEY,
                result TEXT NOT NULL,
                executed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS pre_experiment_error_log_archive (
                original_id INTEGER PRIMARY KEY,
                payload_json TEXT NOT NULL,
                archived_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        previous = conn.execute(
            text("SELECT result FROM app_one_time_maintenance WHERE key = :key"),
            {"key": LEGACY_ERROR_ARCHIVE_KEY},
        ).scalar_one_or_none()
        if previous is not None:
            return {**json.loads(previous), "status": "already_processed"}

        original_rows = conn.execute(
            text("SELECT * FROM error_logs ORDER BY id")
        ).mappings().all()
        original_ids = []
        for row in original_rows:
            source = dict(row)
            original_ids.append(int(source["id"]))
            conn.execute(text("""
                INSERT INTO pre_experiment_error_log_archive (original_id, payload_json)
                VALUES (:id, :payload)
            """), {
                "id": source["id"],
                "payload": json.dumps(source, ensure_ascii=False, default=str),
            })
        if original_ids:
            stmt = text("DELETE FROM error_logs WHERE id IN :ids").bindparams(
                bindparam("ids", expanding=True))
            count = conn.execute(stmt, {"ids": original_ids}).rowcount
            if count != len(original_ids):
                raise RuntimeError("Archive-and-clear count mismatch: transaction rolled back")

        result = {
            "status": "archived", "archived": len(original_ids),
            "first_id": min(original_ids) if original_ids else None,
            "last_id": max(original_ids) if original_ids else None,
        }
        conn.execute(text("""
            INSERT INTO app_one_time_maintenance (key, result)
            VALUES (:key, :result)
        """), {
            "key": LEGACY_ERROR_ARCHIVE_KEY,
            "result": json.dumps(result, ensure_ascii=False),
        })
        return result
