"""Run database schema maintenance once per deployed schema revision.

A Free Render instance may be stopped and restarted frequently. Running the
legacy-class migration, schema ALTER checks and historical UPDATE statements
on every cold start makes the QR endpoint slower to become available.

The marker is durable in PostgreSQL. Increment ``SCHEMA_MARKER`` whenever a
future release adds a new schema/data migration. Do not store the marker on
Render's ephemeral filesystem. Error-log cleanup still has its own independent
one-time marker and is never re-armed by this optimization.
"""

import json
from sqlalchemy import text

SCHEMA_MARKER = "schema_initialized_v4332"
STARTUP_LOCK_ID = 433200032


def prepare_database_once(db, ensure_schema_upgrades, migrate_legacy_classes,
                          cleanup_one_time):
    """Upgrade a new/old database on first launch; read one marker thereafter.

    Serialize workers with a session-scoped PostgreSQL advisory lock. The
    connection used for the lock stays open while SQLAlchemy performs the
    actual migrations on other connections. A failed migration leaves the
    marker absent so a later restart can retry rather than hiding a fault.
    """
    engine = db.engine
    with engine.connect() as lock_conn:
        is_postgres = engine.dialect.name == "postgresql"
        if is_postgres:
            lock_conn.execute(text("SELECT pg_advisory_lock(:key)"), {"key": STARTUP_LOCK_ID})
            lock_conn.commit()
        try:
            lock_conn.execute(text("""
                CREATE TABLE IF NOT EXISTS app_one_time_maintenance (
                    key VARCHAR(100) PRIMARY KEY,
                    result TEXT NOT NULL,
                    executed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            lock_conn.commit()
            already_done = lock_conn.execute(
                text("SELECT result FROM app_one_time_maintenance WHERE key=:key"),
                {"key": SCHEMA_MARKER},
            ).scalar_one_or_none()
            lock_conn.commit()
            if already_done is not None:
                return False

            db.create_all()
            ensure_schema_upgrades()
            migrate_legacy_classes()
            # This function retains its *own* marker from v4.3.28. Never
            # delete new logs or run the old cleanup a second time.
            cleanup_one_time(engine)

            lock_conn.execute(text("""
                INSERT INTO app_one_time_maintenance (key, result)
                VALUES (:key, :result)
            """), {"key": SCHEMA_MARKER,
                   "result": json.dumps({"status": "completed", "version": "4.3.32"})})
            lock_conn.commit()
            return True
        except Exception:
            lock_conn.rollback()
            raise
        finally:
            if is_postgres:
                lock_conn.execute(text("SELECT pg_advisory_unlock(:key)"),
                                  {"key": STARTUP_LOCK_ID})
                lock_conn.commit()
