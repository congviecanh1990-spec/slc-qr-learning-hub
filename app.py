from __future__ import annotations

import csv
import io
import json
import os
import secrets
import zipfile
import time
from datetime import timedelta
from functools import wraps
from urllib.parse import urlparse

import qrcode
import requests
from authlib.integrations.flask_client import OAuth
from flask import (
    Flask, Response, abort, current_app, flash, jsonify, redirect,
    render_template, request, send_file, session, url_for
)
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import func, text, DateTime
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from models import (
    db, User, OAuthAccount, YouTubeChannel, Playlist, Video, PlaylistVideo, Course, ClassGroup,
    Participant, QrCode, QrTargetHistory, ScanLog, WatchSession, WatchEvent,
    HubSubscription, HubEvent, ErrorLog, ExperimentRun, FunctionalTestRun,
    SurveyResult, utcnow
)
from security import encrypt_json
from services.youtube import sync_my_channel, sync_video_ids, reconcile_user
from services.websub import subscribe_channel, verify_callback, parse_notification

csrf = CSRFProtect()
oauth = OAuth()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)
    csrf.init_app(app)
    oauth.init_app(app)

    if app.config["GOOGLE_CLIENT_ID"] and app.config["GOOGLE_CLIENT_SECRET"]:
        oauth.register(
            name="google",
            client_id=app.config["GOOGLE_CLIENT_ID"],
            client_secret=app.config["GOOGLE_CLIENT_SECRET"],
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": app.config["GOOGLE_SCOPES"]},
        )

    register_routes(app)

    with app.app_context():
        if app.config["AUTO_CREATE_DB"]:
            db.create_all()

    return app


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper


def current_user():
    uid = session.get("user_id")
    return db.session.get(User, uid) if uid else None


def safe_next(value):
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc:
        return None
    if not value.startswith("/"):
        return None
    return value


def base_url():
    return current_app.config.get("BASE_URL") or request.url_root.rstrip("/")


def qr_public_url(qr):
    return f"{base_url()}/q/{qr.slug}"


def active_video_for_qr(qr):
    target = qr.current_target
    return target.video if target else None


def owner_filter(model):
    user = current_user()
    if user.role == "admin":
        return model.query
    if hasattr(model, "owner_id"):
        return model.query.filter_by(owner_id=user.id)
    return model.query


def register_routes(app):
    @app.context_processor
    def inject_globals():
        return {
            "me": current_user(),
            "heartbeat_seconds": current_app.config["HEARTBEAT_SECONDS"],
            "completion_threshold": current_app.config["COMPLETION_THRESHOLD"],
        }

    @app.get("/health")
    def health():
        try:
            db.session.execute(text("SELECT 1"))
            return jsonify({"status": "ok", "database": "ok"})
        except Exception as exc:
            return jsonify({"status": "error", "detail": str(exc)}), 500

    @app.get("/")
    def index():
        user = current_user()
        if not user:
            return render_template("landing.html")
        videos = Video.query.join(YouTubeChannel).filter(YouTubeChannel.user_id == user.id).count() if user.role != "admin" else Video.query.count()
        qrs = QrCode.query.filter_by(owner_id=user.id).count() if user.role != "admin" else QrCode.query.count()
        scan_q = ScanLog.query.join(QrCode, ScanLog.qr_id == QrCode.id)
        watch_q = WatchSession.query.join(QrCode, WatchSession.qr_id == QrCode.id)
        if user.role != "admin":
            scan_q = scan_q.filter(QrCode.owner_id == user.id)
            watch_q = watch_q.filter(QrCode.owner_id == user.id)
        scans = scan_q.count()
        watch = watch_q.count()
        completed = watch_q.filter(WatchSession.completed.is_(True)).count()
        completion_rate = round(100 * completed / watch, 1) if watch else 0
        recent_scans = scan_q.order_by(ScanLog.scanned_at.desc()).limit(10).all()
        return render_template("dashboard.html", videos=videos, qrs=qrs, scans=scans, watch=watch,
                               completion_rate=completion_rate, recent_scans=recent_scans)

    @app.get("/auth/login")
    def login():
        if not current_app.config["GOOGLE_CLIENT_ID"]:
            flash("Chưa cấu hình GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET.", "danger")
            return redirect(url_for("index"))
        redirect_uri = f"{base_url()}/auth/callback"
        session["after_login"] = safe_next(request.args.get("next")) or url_for("index")
        return oauth.google.authorize_redirect(
            redirect_uri,
            access_type="offline",
            prompt="consent",
            include_granted_scopes="true",
        )

    @app.get("/auth/callback")
    def auth_callback():
        try:
            token = oauth.google.authorize_access_token()
            access_token = token.get("access_token")
            if not access_token:
                raise RuntimeError("Google không trả về access_token")
            profile = requests.get(
                "https://openidconnect.googleapis.com/v1/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=20,
            )
            profile.raise_for_status()
            info = profile.json()
            email = (info.get("email") or "").lower().strip()
            if not email:
                raise RuntimeError("Không đọc được email từ Google")
            user = User.query.filter_by(email=email).first()
            if not user:
                role = "admin" if email in current_app.config["ADMIN_EMAILS"] else "lecturer"
                user = User(email=email, name=info.get("name") or email, google_sub=info.get("sub"), role=role)
                db.session.add(user)
                db.session.flush()
            else:
                user.name = info.get("name") or user.name
                user.google_sub = info.get("sub") or user.google_sub
                if email in current_app.config["ADMIN_EMAILS"]:
                    user.role = "admin"
            user.last_login_at = utcnow()

            account = OAuthAccount.query.filter_by(user_id=user.id).first()
            existing_refresh = None
            if account:
                try:
                    from security import decrypt_json
                    existing_refresh = decrypt_json(account.token_encrypted).get("refresh_token")
                except Exception:
                    existing_refresh = None
            if existing_refresh and not token.get("refresh_token"):
                token["refresh_token"] = existing_refresh
            if not account:
                account = OAuthAccount(user_id=user.id, provider="google", token_encrypted="")
                db.session.add(account)
            account.token_encrypted = encrypt_json(token)
            token_scope = token.get("scope") or current_app.config["GOOGLE_SCOPES"]
            account.scopes = " ".join(token_scope) if isinstance(token_scope, (list, tuple)) else str(token_scope)
            db.session.commit()
            session["user_id"] = user.id
            session.permanent = True
            flash("Đăng nhập Google/YouTube thành công.", "success")
            return redirect(session.pop("after_login", url_for("index")))
        except Exception as exc:
            db.session.rollback()
            db.session.add(ErrorLog(module="oauth", message="Đăng nhập Google thất bại", details=str(exc)))
            db.session.commit()
            flash(f"Đăng nhập thất bại: {exc}", "danger")
            return redirect(url_for("index"))

    @app.get("/auth/logout")
    def logout():
        session.clear()
        return redirect(url_for("index"))

    @app.get("/youtube")
    @login_required
    def youtube_page():
        user = current_user()
        channels = YouTubeChannel.query.filter_by(user_id=user.id).all()
        channel_ids = [c.id for c in channels]
        hub_events = HubEvent.query.filter(HubEvent.channel_id.in_(channel_ids)).order_by(HubEvent.received_at.desc()).limit(20).all() if channel_ids else []
        return render_template("youtube.html", channels=channels, hub_events=hub_events)

    @app.post("/youtube/sync")
    @login_required
    def youtube_sync():
        try:
            channels = sync_my_channel(current_user())
            flash(f"Đã đồng bộ {len(channels)} kênh YouTube.", "success")
        except Exception as exc:
            flash(f"Đồng bộ thất bại: {exc}", "danger")
        return redirect(url_for("youtube_page"))

    @app.post("/youtube/websub/<int:channel_pk>/subscribe")
    @login_required
    def youtube_websub_subscribe(channel_pk):
        channel = db.session.get(YouTubeChannel, channel_pk) or abort(404)
        user = current_user()
        if user.role != "admin" and channel.user_id != user.id:
            abort(403)
        try:
            subscribe_channel(channel)
            flash("Đã gửi yêu cầu đăng ký Hub/WebSub. Chờ Hub xác minh callback.", "success")
        except Exception as exc:
            flash(f"Đăng ký Hub/WebSub thất bại: {exc}", "danger")
        return redirect(url_for("youtube_page"))

    @app.route("/websub/callback/<channel_youtube_id>/<secret>", methods=["GET", "POST"])
    @csrf.exempt
    def websub_callback(channel_youtube_id, secret):
        channel = YouTubeChannel.query.filter_by(channel_id=channel_youtube_id).first_or_404()
        if request.method == "GET":
            challenge = verify_callback(channel, secret, request.args)
            if challenge is None:
                abort(404)
            return Response(challenge, mimetype="text/plain")

        sub = HubSubscription.query.filter_by(channel_id=channel.id, callback_secret=secret).first()
        if not sub:
            abort(404)
        evt = parse_notification(channel, request.data)
        if evt.youtube_video_id:
            try:
                sync_video_ids(channel.user, channel, [evt.youtube_video_id])
                evt.processed = True
                db.session.commit()
            except Exception as exc:
                db.session.add(ErrorLog(module="websub", message="Nhận Hub nhưng đồng bộ video lỗi", details=str(exc)))
                db.session.commit()
        return "", 204

    @app.get("/videos")
    @login_required
    def videos_page():
        user = current_user()
        q = Video.query.join(YouTubeChannel)
        if user.role != "admin":
            q = q.filter(YouTubeChannel.user_id == user.id)
        status = request.args.get("status")
        if status == "private":
            q = q.filter(Video.privacy_status == "private")
        elif status == "noembed":
            q = q.filter(Video.embeddable.is_(False))
        elif status == "unavailable":
            q = q.filter(Video.is_available.is_(False))
        videos = q.order_by(Video.published_at.desc().nullslast(), Video.id.desc()).all()
        return render_template("videos.html", videos=videos, status=status)

    @app.route("/courses", methods=["GET", "POST"])
    @login_required
    def courses_page():
        user = current_user()
        if request.method == "POST":
            code = request.form.get("code", "").strip()
            name = request.form.get("name", "").strip()
            unit = request.form.get("unit_name", "").strip()
            if not code or not name:
                flash("Cần nhập mã và tên học phần.", "warning")
            else:
                try:
                    db.session.add(Course(owner_id=user.id, code=code, name=name, unit_name=unit))
                    db.session.commit()
                    flash("Đã thêm học phần.", "success")
                except Exception as exc:
                    db.session.rollback()
                    flash(f"Không thêm được học phần: {exc}", "danger")
            return redirect(url_for("courses_page"))
        courses = Course.query.filter_by(owner_id=user.id).order_by(Course.created_at.desc()).all()
        return render_template("courses.html", courses=courses)

    @app.post("/courses/<int:course_id>/classes")
    @login_required
    def add_class(course_id):
        course = db.session.get(Course, course_id) or abort(404)
        user = current_user()
        if user.role != "admin" and course.owner_id != user.id:
            abort(403)
        code = request.form.get("code", "").strip()
        name = request.form.get("name", "").strip()
        if code and name:
            try:
                db.session.add(ClassGroup(course_id=course.id, code=code, name=name))
                db.session.commit()
                flash("Đã thêm lớp.", "success")
            except Exception as exc:
                db.session.rollback()
                flash(f"Không thêm được lớp: {exc}", "danger")
        return redirect(url_for("courses_page"))

    @app.route("/qr", methods=["GET", "POST"])
    @login_required
    def qr_page():
        user = current_user()
        if request.method == "POST":
            title = request.form.get("title", "").strip()
            video_id = request.form.get("video_id", type=int)
            course_id = request.form.get("course_id", type=int)
            video = db.session.get(Video, video_id) if video_id else None
            course = db.session.get(Course, course_id) if course_id else None
            if not title or not video:
                flash("Cần nhập tên QR và chọn video.", "warning")
            else:
                t0 = time.perf_counter()
                slug = secrets.token_urlsafe(8).replace("-", "").replace("_", "")[:12]
                qr = QrCode(owner_id=user.id, course_id=course.id if course else None, slug=slug, title=title)
                db.session.add(qr)
                db.session.flush()
                db.session.add(QrTargetHistory(qr_id=qr.id, video_id=video.id, changed_by=user.id))
                db.session.commit()
                qr.processing_seconds = round(time.perf_counter() - t0, 4)
                db.session.commit()
                flash(f"Đã tạo QR động trong {qr.processing_seconds:.3f} giây.", "success")
            return redirect(url_for("qr_page"))

        qrs = QrCode.query.filter_by(owner_id=user.id).order_by(QrCode.created_at.desc()).all()
        videos = Video.query.join(YouTubeChannel).filter(YouTubeChannel.user_id == user.id, Video.is_available.is_(True)).order_by(Video.title).all()
        courses = Course.query.filter_by(owner_id=user.id, active=True).order_by(Course.name).all()
        return render_template("qr.html", qrs=qrs, videos=videos, courses=courses)

    @app.post("/qr/<int:qr_id>/retarget")
    @login_required
    def qr_retarget(qr_id):
        qr = db.session.get(QrCode, qr_id) or abort(404)
        user = current_user()
        if user.role != "admin" and qr.owner_id != user.id:
            abort(403)
        video_id = request.form.get("video_id", type=int)
        video = db.session.get(Video, video_id) or abort(400)
        now = utcnow()
        old = qr.current_target
        if old:
            old.active_to = now
        db.session.add(QrTargetHistory(qr_id=qr.id, video_id=video.id, active_from=now, changed_by=user.id))
        db.session.commit()
        flash("Đã đổi video đích. Slug và mã QR không thay đổi.", "success")
        return redirect(url_for("qr_page"))

    @app.get("/qr/<int:qr_id>/png")
    @login_required
    def qr_png(qr_id):
        qr = db.session.get(QrCode, qr_id) or abort(404)
        user = current_user()
        if user.role != "admin" and qr.owner_id != user.id:
            abort(403)
        img = qrcode.make(qr_public_url(qr))
        bio = io.BytesIO()
        img.save(bio, format="PNG")
        bio.seek(0)
        return send_file(bio, mimetype="image/png", as_attachment=True, download_name=f"QR_{qr.slug}.png")

    @app.get("/qr/download-all.zip")
    @login_required
    def qr_download_all():
        user = current_user()
        qrs = QrCode.query.all() if user.role == "admin" else QrCode.query.filter_by(owner_id=user.id).all()
        bio = io.BytesIO()
        with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
            for q in qrs:
                img = qrcode.make(qr_public_url(q))
                png = io.BytesIO()
                img.save(png, format="PNG")
                zf.writestr(f"QR_{q.slug}.png", png.getvalue())
        bio.seek(0)
        return send_file(bio, mimetype="application/zip", as_attachment=True, download_name="SLC_QR_ALL.zip")

    @app.get("/q/<slug>")
    def public_qr(slug):
        qr = QrCode.query.filter_by(slug=slug, active=True).first_or_404()
        video = active_video_for_qr(qr)
        if not session.get("participant_code"):
            session["identify_next"] = url_for("public_qr", slug=slug)
            course = qr.course
            classes = course.classes if course else []
            return render_template("identify.html", qr=qr, classes=classes)

        pcode = session.get("participant_code")
        role = session.get("participant_role", "SV")
        class_code = session.get("participant_class_code")
        success = bool(video and video.is_available and video.embeddable is not False and video.privacy_status != "private")

        cutoff = utcnow() - timedelta(seconds=30)
        existing = ScanLog.query.filter(
            ScanLog.participant_code == pcode,
            ScanLog.qr_id == qr.id,
            ScanLog.scanned_at >= cutoff,
        ).first()
        if not existing:
            db.session.add(ScanLog(
                participant_code=pcode,
                role=role,
                class_code=class_code,
                course_id=qr.course_id,
                qr_id=qr.id,
                video_id=video.id if video else None,
                success=success,
            ))
            db.session.commit()

        if not video:
            return render_template("viewer_error.html", qr=qr, message="QR chưa được gán video đích."), 404
        if not success:
            return render_template("viewer_error.html", qr=qr, message=f"Video hiện không thể phát trong trang học liệu ({video.status_label})."), 409
        return render_template("viewer.html", qr=qr, video=video)

    @app.post("/identify")
    def identify():
        code = request.form.get("participant_code", "").strip()
        role = request.form.get("role", "SV").strip().upper()
        class_code = request.form.get("class_code", "").strip()
        if not code:
            flash("Vui lòng nhập mã GV/SV.", "warning")
            return redirect(session.get("identify_next") or url_for("index"))
        if role not in {"GV", "SV"}:
            role = "SV"
        session["participant_code"] = code[:128]
        session["participant_role"] = role
        session["participant_class_code"] = class_code[:64]
        nxt = session.pop("identify_next", None) or url_for("index")
        return redirect(nxt)

    @app.post("/participant/reset")
    def participant_reset():
        for k in ("participant_code", "participant_role", "participant_class_code"):
            session.pop(k, None)
        return redirect(request.referrer or url_for("index"))

    @app.post("/api/watch/start")
    def watch_start():
        data = request.get_json(silent=True) or {}
        slug = data.get("slug")
        qr = QrCode.query.filter_by(slug=slug, active=True).first_or_404()
        video = active_video_for_qr(qr)
        if not session.get("participant_code") or not video:
            return jsonify({"error": "missing_participant_or_video"}), 400
        ws = WatchSession(
            session_key=secrets.token_urlsafe(24),
            participant_code=session["participant_code"],
            role=session.get("participant_role", "SV"),
            class_code=session.get("participant_class_code"),
            course_id=qr.course_id,
            qr_id=qr.id,
            video_id=video.id,
            duration_seconds=float(data.get("duration") or 0),
        )
        db.session.add(ws)
        db.session.commit()
        return jsonify({"session_key": ws.session_key})

    @app.post("/api/watch/event")
    def watch_event():
        data = request.get_json(silent=True) or {}
        key = data.get("session_key")
        ws = WatchSession.query.filter_by(session_key=key).first_or_404()
        if session.get("participant_code") != ws.participant_code:
            abort(403)
        event_type = (data.get("event_type") or "heartbeat").lower()[:24]
        state = (data.get("state") or "unknown").lower()[:16]
        position = max(0.0, float(data.get("position") or 0))
        duration = max(0.0, float(data.get("duration") or ws.duration_seconds or 0))
        now = utcnow()
        elapsed = max(0.0, (now - ws.last_event_at).total_seconds()) if ws.last_event_at else 0.0
        position_delta = position - (ws.last_position or 0.0)
        counted = 0.0

        # Chỉ cộng khi phiên trước đang phát, thời gian thực hợp lý và không có bước nhảy tua lớn.
        if ws.last_state == "playing" and elapsed <= max(15, current_app.config["HEARTBEAT_SECONDS"] * 3):
            if -1.0 <= position_delta <= elapsed + 3.0:
                counted = max(0.0, min(elapsed, position_delta + 0.5))
                ws.estimated_watch_seconds += counted

        ws.max_position = max(ws.max_position or 0.0, position)
        ws.duration_seconds = max(ws.duration_seconds or 0.0, duration)
        ws.last_event_at = now
        ws.last_position = position
        ws.last_state = state

        if ws.duration_seconds > 0:
            ws.completion_percent = min(100.0, 100.0 * ws.estimated_watch_seconds / ws.duration_seconds)
        if event_type == "ended" or state == "ended":
            ws.completed = True
            ws.ended_at = now
            ws.completion_percent = max(ws.completion_percent, 100.0)
        elif ws.duration_seconds > 0 and ws.estimated_watch_seconds / ws.duration_seconds >= current_app.config["COMPLETION_THRESHOLD"]:
            ws.completed = True

        db.session.add(WatchEvent(
            watch_session_id=ws.id,
            event_type=event_type,
            player_state=state,
            position=position,
            duration=duration,
            counted_seconds=counted,
        ))
        db.session.commit()
        return jsonify({
            "ok": True,
            "estimated_watch_seconds": round(ws.estimated_watch_seconds, 1),
            "max_position": round(ws.max_position, 1),
            "completion_percent": round(ws.completion_percent, 1),
            "completed": ws.completed,
        })

    @app.get("/analytics")
    @login_required
    def analytics():
        user = current_user()
        scan_q = ScanLog.query.join(QrCode, ScanLog.qr_id == QrCode.id)
        watch_q = WatchSession.query.join(QrCode, WatchSession.qr_id == QrCode.id)
        if user.role != "admin":
            scan_q = scan_q.filter(QrCode.owner_id == user.id)
            watch_q = watch_q.filter(QrCode.owner_id == user.id)

        participant = request.args.get("participant", "").strip()
        role = request.args.get("role", "").strip()
        class_code = request.args.get("class_code", "").strip()
        qr_slug = request.args.get("qr", "").strip()
        if participant:
            scan_q = scan_q.filter(ScanLog.participant_code.ilike(f"%{participant}%"))
            watch_q = watch_q.filter(WatchSession.participant_code.ilike(f"%{participant}%"))
        if role in {"GV", "SV"}:
            scan_q = scan_q.filter(ScanLog.role == role)
            watch_q = watch_q.filter(WatchSession.role == role)
        if class_code:
            scan_q = scan_q.filter(ScanLog.class_code == class_code)
            watch_q = watch_q.filter(WatchSession.class_code == class_code)
        if qr_slug:
            scan_q = scan_q.filter(QrCode.slug == qr_slug)
            watch_q = watch_q.filter(QrCode.slug == qr_slug)

        scans = scan_q.order_by(ScanLog.scanned_at.desc()).limit(500).all()
        watches = watch_q.order_by(WatchSession.started_at.desc()).limit(500).all()

        day_q = db.session.query(func.date(ScanLog.scanned_at), func.count(ScanLog.id)).join(QrCode, ScanLog.qr_id == QrCode.id)
        if user.role != "admin":
            day_q = day_q.filter(QrCode.owner_id == user.id)
        by_day = day_q.group_by(func.date(ScanLog.scanned_at)).order_by(func.date(ScanLog.scanned_at)).limit(30).all()
        chart_labels = [str(x[0]) for x in by_day]
        chart_values = [x[1] for x in by_day]
        return render_template("analytics.html", scans=scans, watches=watches,
                               chart_labels=chart_labels, chart_values=chart_values)

    @app.get("/exports/scans.csv")
    @login_required
    def export_scans():
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(["scan_id", "participant_code", "role", "class_code", "course", "qr_slug", "video_id", "scanned_at", "success"])
        user = current_user()
        q = ScanLog.query.join(QrCode, ScanLog.qr_id == QrCode.id)
        if user.role != "admin":
            q = q.filter(QrCode.owner_id == user.id)
        for s in q.order_by(ScanLog.scanned_at).all():
            w.writerow([s.id, s.participant_code, s.role, s.class_code, s.course.code if s.course else "", s.qr.slug if s.qr else "", s.video.youtube_video_id if s.video else "", s.scanned_at.isoformat(), int(s.success)])
        return Response(out.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=scan_logs.csv"})

    @app.get("/exports/watch.csv")
    @login_required
    def export_watch():
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(["session_key", "participant_code", "role", "class_code", "qr_slug", "video_id", "started_at", "estimated_watch_seconds", "max_position", "duration_seconds", "completion_percent", "completed"])
        user = current_user()
        q = WatchSession.query.join(QrCode, WatchSession.qr_id == QrCode.id)
        if user.role != "admin":
            q = q.filter(QrCode.owner_id == user.id)
        for s in q.order_by(WatchSession.started_at).all():
            w.writerow([s.session_key, s.participant_code, s.role, s.class_code, s.qr.slug if s.qr else "", s.video.youtube_video_id if s.video else "", s.started_at.isoformat(), round(s.estimated_watch_seconds, 2), round(s.max_position, 2), round(s.duration_seconds, 2), round(s.completion_percent, 2), int(s.completed)])
        return Response(out.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=watch_sessions.csv"})

    @app.route("/research", methods=["GET", "POST"])
    @login_required
    def research_page():
        user = current_user()
        if request.method == "POST":
            form_type = request.form.get("form_type")
            try:
                if form_type == "experiment":
                    db.session.add(ExperimentRun(
                        owner_id=user.id,
                        task_key=request.form.get("task_key", "").strip(),
                        mode=request.form.get("mode", "manual"),
                        operations_count=int(request.form.get("operations_count") or 0),
                        elapsed_seconds=float(request.form.get("elapsed_seconds") or 0),
                        system_processing_seconds=float(request.form.get("system_processing_seconds") or 0) or None,
                        success=request.form.get("success") == "1",
                        note=request.form.get("note", "").strip(),
                    ))
                elif form_type == "test":
                    db.session.add(FunctionalTestRun(
                        owner_id=user.id,
                        case_code=request.form.get("case_code", "").strip(),
                        case_name=request.form.get("case_name", "").strip(),
                        passed=request.form.get("passed") == "1",
                        note=request.form.get("note", "").strip(),
                    ))
                elif form_type == "survey":
                    rating = int(request.form.get("rating") or 0)
                    if rating < 1 or rating > 5:
                        raise ValueError("Điểm khảo sát phải từ 1 đến 5")
                    db.session.add(SurveyResult(
                        owner_id=user.id,
                        respondent_type=request.form.get("respondent_type", "SV"),
                        respondent_code=request.form.get("respondent_code", "").strip(),
                        rating=rating,
                        note=request.form.get("note", "").strip(),
                    ))
                db.session.commit()
                flash("Đã ghi nhận dữ liệu nghiên cứu.", "success")
            except Exception as exc:
                db.session.rollback()
                flash(f"Không lưu được dữ liệu: {exc}", "danger")
            return redirect(url_for("research_page"))

        metrics = acceptance_metrics(user)
        experiments = ExperimentRun.query.filter_by(owner_id=user.id).order_by(ExperimentRun.created_at.desc()).limit(50).all()
        tests = FunctionalTestRun.query.filter_by(owner_id=user.id).order_by(FunctionalTestRun.created_at.desc()).limit(50).all()
        surveys = SurveyResult.query.filter_by(owner_id=user.id).order_by(SurveyResult.created_at.desc()).limit(50).all()
        return render_template("research.html", metrics=metrics, experiments=experiments, tests=tests, surveys=surveys)

    @app.get("/admin/backup.zip")
    @login_required
    def backup_zip():
        user = current_user()
        if user.role != "admin":
            abort(403)
        bio = build_backup_zip()
        return send_file(bio, mimetype="application/zip", as_attachment=True, download_name=f"slc_qr_backup_{utcnow().date().isoformat()}.zip")

    @app.route("/admin/restore", methods=["GET", "POST"])
    @login_required
    def restore_backup():
        user = current_user()
        if user.role != "admin":
            abort(403)
        if request.method == "POST":
            upload = request.files.get("backup_file")
            confirm = request.form.get("confirm")
            if not upload or confirm != "RESTORE":
                flash("Chọn tệp backup ZIP và nhập RESTORE để xác nhận.", "warning")
                return redirect(url_for("restore_backup"))
            try:
                restore_from_zip(upload.stream)
                session.clear()
                flash("Khôi phục dữ liệu thành công. Vui lòng đăng nhập lại.", "success")
                return redirect(url_for("index"))
            except Exception as exc:
                db.session.rollback()
                db.session.add(ErrorLog(module="restore", message="Khôi phục backup thất bại", details=str(exc)))
                db.session.commit()
                flash(f"Khôi phục thất bại: {exc}", "danger")
                return redirect(url_for("restore_backup"))
        return render_template("restore.html")

    @app.get("/errors")
    @login_required
    def error_logs_page():
        if current_user().role != "admin":
            abort(403)
        logs = ErrorLog.query.order_by(ErrorLog.created_at.desc()).limit(300).all()
        return render_template("errors.html", logs=logs)

    @app.post("/tasks/reconcile")
    @csrf.exempt
    def task_reconcile():
        key = request.headers.get("X-Task-Key") or request.args.get("key")
        if not secrets.compare_digest(str(key or ""), str(current_app.config["RECONCILE_KEY"])):
            abort(403)
        total = 0
        results = []
        for user in User.query.all():
            if not user.oauth_account:
                continue
            try:
                count = reconcile_user(user)
                total += count
                results.append({"user": user.email, "videos": count, "ok": True})
            except Exception as exc:
                db.session.add(ErrorLog(module="reconcile", message=f"Đối soát lỗi: {user.email}", details=str(exc)))
                db.session.commit()
                results.append({"user": user.email, "ok": False, "error": str(exc)})
        return jsonify({"ok": True, "total_videos": total, "results": results})



BACKUP_VERSION = "1.0"

def backup_table_specs():
    return [
        ("users", User),
        ("oauth_accounts", OAuthAccount),
        ("youtube_channels", YouTubeChannel),
        ("playlists", Playlist),
        ("videos", Video),
        ("playlist_videos", PlaylistVideo),
        ("courses", Course),
        ("class_groups", ClassGroup),
        ("participants", Participant),
        ("qr_codes", QrCode),
        ("qr_target_history", QrTargetHistory),
        ("scan_logs", ScanLog),
        ("watch_sessions", WatchSession),
        ("watch_events", WatchEvent),
        ("hub_subscriptions", HubSubscription),
        ("hub_events", HubEvent),
        ("error_logs", ErrorLog),
        ("experiment_runs", ExperimentRun),
        ("functional_test_runs", FunctionalTestRun),
        ("survey_results", SurveyResult),
    ]

def build_backup_zip():
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
        manifest = {
            "product": "SLC QR Learning Hub",
            "backup_version": BACKUP_VERSION,
            "created_at": utcnow().isoformat(),
            "warning": "OAuth token được lưu ở dạng mã hóa; không chia sẻ tệp backup công khai."
        }
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for name, model in backup_table_specs():
            data = [serialize_model(row) for row in model.query.all()]
            zf.writestr(f"{name}.json", json.dumps(data, ensure_ascii=False, indent=2, default=str))
    bio.seek(0)
    return bio

def restore_from_zip(fileobj):
    raw = fileobj.read()
    if len(raw) > 50 * 1024 * 1024:
        raise ValueError("Tệp backup vượt quá 50 MB.")
    with zipfile.ZipFile(io.BytesIO(raw), "r") as zf:
        names = set(zf.namelist())
        if "manifest.json" not in names:
            raise ValueError("Không có manifest.json; đây không phải backup hợp lệ.")
        manifest = json.loads(zf.read("manifest.json"))
        if manifest.get("backup_version") != BACKUP_VERSION:
            raise ValueError("Phiên bản backup không tương thích.")
        payload = {}
        for name, model in backup_table_specs():
            fn = f"{name}.json"
            if fn not in names:
                raise ValueError(f"Thiếu {fn} trong backup.")
            rows = json.loads(zf.read(fn))
            columns = {c.name: c for c in model.__table__.columns}
            cleaned = []
            for row in rows:
                item = {}
                for k, v in row.items():
                    col = columns.get(k)
                    if not col:
                        continue
                    if v is not None and isinstance(col.type, DateTime) and isinstance(v, str):
                        from datetime import datetime
                        v = datetime.fromisoformat(v.replace("Z", "+00:00"))
                    item[k] = v
                cleaned.append(item)
            payload[name] = cleaned

    # Xóa theo thứ tự ngược để tôn trọng khóa ngoại, sau đó chèn lại theo thứ tự cha -> con.
    for _, model in reversed(backup_table_specs()):
        db.session.execute(model.__table__.delete())
    db.session.flush()
    for name, model in backup_table_specs():
        rows = payload[name]
        if rows:
            db.session.execute(model.__table__.insert(), rows)
    db.session.commit()

    # Đồng bộ lại sequence PostgreSQL sau khi khôi phục ID tường minh.
    if db.engine.dialect.name == "postgresql":
        for _, model in backup_table_specs():
            table = model.__tablename__
            if "id" in model.__table__.columns:
                db.session.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('{table}','id'), COALESCE((SELECT MAX(id) FROM {table}), 1), (SELECT MAX(id) IS NOT NULL FROM {table}))"
                ))
        db.session.commit()

def acceptance_metrics(user):
    scan_q = ScanLog.query.join(QrCode, ScanLog.qr_id == QrCode.id)
    if user.role != "admin":
        scan_q = scan_q.filter(QrCode.owner_id == user.id)
    scans_total = scan_q.count()
    scans_success = scan_q.filter(ScanLog.success.is_(True)).count()
    scan_rate = round(100 * scans_success / scans_total, 1) if scans_total else None

    tests_total = FunctionalTestRun.query.filter_by(owner_id=user.id).count()
    tests_pass = FunctionalTestRun.query.filter_by(owner_id=user.id, passed=True).count()
    test_rate = round(100 * tests_pass / tests_total, 1) if tests_total else None

    manual = ExperimentRun.query.filter_by(owner_id=user.id, mode="manual").all()
    webapp = ExperimentRun.query.filter_by(owner_id=user.id, mode="webapp").all()
    manual_ops = sum(x.operations_count for x in manual) / len(manual) if manual else None
    app_ops = sum(x.operations_count for x in webapp) / len(webapp) if webapp else None
    manual_time = sum(x.elapsed_seconds for x in manual) / len(manual) if manual else None
    app_time = sum(x.elapsed_seconds for x in webapp) / len(webapp) if webapp else None
    qr_perf_q = QrCode.query.filter(QrCode.processing_seconds.isnot(None))
    if user.role != "admin":
        qr_perf_q = qr_perf_q.filter(QrCode.owner_id == user.id)
    qr_perf = [q.processing_seconds for q in qr_perf_q.all() if q.processing_seconds is not None]
    processing_values = qr_perf or [x.system_processing_seconds for x in webapp if x.system_processing_seconds is not None]
    avg_processing = sum(processing_values) / len(processing_values) if processing_values else None

    reduction_ops = round(100 * (manual_ops - app_ops) / manual_ops, 1) if manual_ops and app_ops is not None else None
    reduction_time = round(100 * (manual_time - app_time) / manual_time, 1) if manual_time and app_time is not None else None

    lecturer_s = SurveyResult.query.filter_by(owner_id=user.id, respondent_type="GV").all()
    student_s = SurveyResult.query.filter_by(owner_id=user.id, respondent_type="SV").all()
    lecturer_sat = round(100 * len([x for x in lecturer_s if x.rating >= 4]) / len(lecturer_s), 1) if lecturer_s else None
    student_sat = round(100 * len([x for x in student_s if x.rating >= 4]) / len(student_s), 1) if student_s else None

    participant_base = db.session.query(ScanLog.participant_code).join(QrCode, ScanLog.qr_id == QrCode.id)
    if user.role != "admin":
        participant_base = participant_base.filter(QrCode.owner_id == user.id)
    gv_count = participant_base.filter(ScanLog.role == "GV").distinct().count()
    sv_count = participant_base.filter(ScanLog.role == "SV").distinct().count()

    video_q = Video.query.join(YouTubeChannel)
    if user.role != "admin":
        video_q = video_q.filter(YouTubeChannel.user_id == user.id)

    return [
        metric("Tỷ lệ QR quét thành công", scan_rate, ">=", 98, "%"),
        metric("Thời gian xử lý hệ thống trung bình/video", round(avg_processing, 2) if avg_processing is not None else None, "<=", 5, " giây"),
        metric("Giảm số thao tác so với thủ công", reduction_ops, ">=", 30, "%"),
        metric("Giảm tổng thời gian so với thủ công", reduction_time, ">=", 30, "%"),
        metric("Tỷ lệ ca kiểm thử chức năng đạt", test_rate, ">=", 95, "%"),
        metric("Số học phần thực nghiệm", Course.query.filter_by(owner_id=user.id).count(), ">=", 3, ""),
        metric("Số đơn vị/khoa/bộ môn", db.session.query(func.count(func.distinct(Course.unit_name))).filter(Course.owner_id == user.id, Course.unit_name.isnot(None), Course.unit_name != "").scalar() or 0, ">=", 2, ""),
        metric("Số giảng viên tham gia", gv_count, ">=", 5, ""),
        metric("Số sinh viên tham gia", sv_count, ">=", 60, ""),
        metric("Số video/tình huống kiểm thử", video_q.count(), ">=", 100, ""),
        metric("Mức hài lòng giảng viên", lecturer_sat, ">=", 80, "%"),
        metric("Mức hài lòng sinh viên", student_sat, ">=", 80, "%"),
    ]


def metric(name, value, op, target, suffix):
    passed = None
    if value is not None:
        passed = value >= target if op == ">=" else value <= target
    return {"name": name, "value": value, "op": op, "target": target, "suffix": suffix, "passed": passed}


def serialize_model(obj):
    out = {}
    for col in obj.__table__.columns:
        value = getattr(obj, col.name)
        if hasattr(value, "isoformat"):
            value = value.isoformat()
        out[col.name] = value
    return out
