"""Render Cron Job / one-off job entry point for YouTube reconciliation."""
from app import create_app
from models import db, User, ErrorLog
from services.youtube import reconcile_user
from services.websub import renew_expiring_subscriptions

app = create_app()

with app.app_context():
    total = 0
    for user in User.query.all():
        if not user.oauth_account:
            continue
        try:
            count = reconcile_user(user)
            total += count
            print(f"OK {user.email}: {count} video")
        except Exception as exc:
            db.session.add(ErrorLog(module="reconcile", message=f"Cron reconcile error: {user.email}", details=str(exc)))
            db.session.commit()
            print(f"ERROR {user.email}: {exc}")
    try:
        renewed = renew_expiring_subscriptions()
        print(f"WEBSUB renewed: {renewed}")
    except Exception as exc:
        db.session.add(ErrorLog(module="websub", message="Cron renew WebSub error", details=str(exc)))
        db.session.commit()
        print(f"WEBSUB ERROR: {exc}")
    print(f"TOTAL {total} video")
