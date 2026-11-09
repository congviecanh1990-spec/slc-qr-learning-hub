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
