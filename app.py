from __future__ import annotations

import csv
import io
import json
import os
import re
import secrets
import unicodedata
import zipfile
import time
from datetime import timedelta, datetime, date
from functools import wraps
from urllib.parse import urlparse

import qrcode
import requests
from PIL import Image
from qrcode.constants import ERROR_CORRECT_H
from authlib.integrations.flask_client import OAuth
from flask import (
    Flask, Response, abort, current_app, flash, jsonify, redirect,
    render_template, request, send_file, session, url_for
)
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import func, text, DateTime, inspect, or_
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from models import (
    db, User, OAuthAccount, YouTubeChannel, Playlist, Video, PlaylistVideo, Course, CourseVideo, CoursePlaylist, ClassGroup,
    SchoolClass, Student, ClassEnrollment, CourseClass, Participant, QrCode, QrTargetHistory, ScanLog, WatchSession, WatchEvent,
    HubSubscription, HubEvent, ErrorLog, ExperimentRun, FunctionalTestRun,
    ResearchSetting, SurveyResult, utcnow
)
from security import encrypt_json
from services.youtube import sync_my_channel, sync_video_ids, reconcile_user
from services.websub import subscribe_channel, verify_callback, parse_notification

csrf = CSRFProtect()
oauth = OAuth()


# Danh mục nhiệm vụ đối chứng được chuẩn hóa theo đúng thiết kế thực nghiệm:
# chỉ so sánh thủ công - Web App cho nhiệm vụ tạo QR riêng và tạo QR hàng loạt.
RESEARCH_COMPARISON_TASKS = [
    {
        "key": "TAO_QR_RIENG",
        "name": "Tạo và lưu mã QR riêng",
        "manual_task": "Tạo và lưu mã QR cho 01 video theo quy trình thủ công",
    },
    {
        "key": "TAO_QR_HANG_LOAT",
        "name": "Tạo và lưu mã QR hàng loạt",
        "manual_task": "Tạo và lưu mã QR cho một nhóm video/playlist theo quy trình thủ công",
    },
]
RESEARCH_COMPARISON_TASK_MAP = {item["key"]: item for item in RESEARCH_COMPARISON_TASKS}


STUDENT_STATUS_LABELS = {
    "dang_hoc": "Đang học",
    "bao_luu": "Bảo lưu",
    "nghi_hoc": "Nghỉ học",
    "chuyen_truong": "Chuyển trường",
    "chuyen_lop": "Chuyển lớp",
    "khac": "Khác",
}


def normalize_student_code(value) -> str:
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return re.sub(r"\s+", "", str(value or "").strip()).upper()[:64]


def enrollment_active_on(enrollment: ClassEnrollment, on_date: date) -> bool:
    return bool(enrollment.started_on <= on_date and (enrollment.ended_on is None or enrollment.ended_on > on_date))


def class_size_at(school_class: SchoolClass, on_date: date | None = None) -> int:
    on_date = on_date or utcnow().date()
    return len({e.student_id for e in school_class.enrollments if enrollment_active_on(e, on_date)})


def student_current_status_in_class(student: Student, school_class: SchoolClass, on_date: date | None = None):
    on_date = on_date or utcnow().date()
    rows = sorted((e for e in student.enrollments if e.school_class_id == school_class.id), key=lambda e: (e.started_on, e.id), reverse=True)
    for e in rows:
        if enrollment_active_on(e, on_date):
            return "dang_hoc", e
    if rows:
        return (rows[0].end_status or "khac"), rows[0]
    return "khac", None


def can_manage_school_class(user: User, school_class: SchoolClass) -> bool:
    return bool(user and (user.role == "admin" or school_class.homeroom_teacher_id == user.id))


def active_enrollments_for_student(student: Student, on_date: date | None = None):
    on_date = on_date or utcnow().date()
    return [e for e in student.enrollments if enrollment_active_on(e, on_date)]


def resolve_student_class_for_qr(student_code: str, qr: QrCode, on_date: date | None = None):
    """Xác định lớp của SV theo mã Nhà trường và thời điểm quét.

    Nếu QR thuộc học phần, SV phải đang thuộc một lớp được gán cho học phần đó.
    """
    on_date = on_date or utcnow().date()
    code = normalize_student_code(student_code)
    student = Student.query.filter_by(student_code=code).first()
    if not student:
        return None, None, "Mã sinh viên chưa có trong danh sách lớp của hệ thống. Vui lòng kiểm tra lại mã hoặc liên hệ giảng viên chủ nhiệm."
    enrollments = active_enrollments_for_student(student, on_date)
    if qr.course_id:
        allowed_ids = {link.school_class_id for link in CourseClass.query.filter_by(course_id=qr.course_id, active=True).all()}
        if not allowed_ids:
            return student, None, "Học phần này chưa được giảng viên gán lớp áp dụng. Vui lòng liên hệ giảng viên phụ trách."
        enrollments = [e for e in enrollments if e.school_class_id in allowed_ids]
    if not enrollments:
        return student, None, "Mã sinh viên không thuộc lớp đang áp dụng cho học phần tại thời điểm hiện tại. Vui lòng liên hệ giảng viên phụ trách."
    if len(enrollments) > 1:
        return student, None, "Hệ thống phát hiện mã sinh viên đang đồng thời thuộc nhiều lớp phù hợp. Vui lòng liên hệ giảng viên chủ nhiệm để kiểm tra dữ liệu lớp."
    return student, enrollments[0].school_class, None


def role_label(role: str) -> str:
    return "Quản trị viên" if role == "admin" else "Giảng viên"



def migrate_legacy_classes():
    """Chuyển dữ liệu lớp cũ theo học phần sang danh mục lớp dùng chung, không xóa dữ liệu cũ."""
    try:
        for old in ClassGroup.query.order_by(ClassGroup.id).all():
            name = (old.name or "").strip()
            if not name:
                continue
            school_class = SchoolClass.query.filter(func.lower(SchoolClass.name) == name.lower()).first()
            if not school_class:
                code = (old.code or f"L{old.id:06d}").strip()
                if SchoolClass.query.filter_by(code=code).first():
                    code = f"LOP{old.id:06d}"
                school_class = SchoolClass(code=code, name=name, active=bool(getattr(old, "active", True)))
                db.session.add(school_class)
                db.session.flush()
            link = CourseClass.query.filter_by(course_id=old.course_id, school_class_id=school_class.id).first()
            if not link:
                db.session.add(CourseClass(course_id=old.course_id, school_class_id=school_class.id, active=bool(getattr(old, "active", True))))
        db.session.commit()
    except Exception:
        db.session.rollback()


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
            ensure_schema_upgrades()
            migrate_legacy_classes()

    return app



def ensure_schema_upgrades():
    """Nâng cấp nhẹ schema khi deploy mà không xóa PostgreSQL hiện có.

    db.create_all() không tự thêm cột vào bảng đã tồn tại. v2.6 tiếp tục giữ nguyên
    dữ liệu cũ, bổ sung khoa/bộ môn (nếu thiếu) và trạng thái hoạt động cho lớp để
    có thể "xóa" lớp khỏi giao diện mà không làm mất dữ liệu lịch sử.
    """
    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())
    with db.engine.begin() as conn:
        if "users" in tables:
            user_columns = {c["name"] for c in inspector.get_columns("users")}
            if "lecturer_code" not in user_columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN lecturer_code VARCHAR(32)"))
                try:
                    conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_lecturer_code ON users (lecturer_code)"))
                except Exception:
                    pass
        if "courses" in tables:
            columns = {c["name"] for c in inspector.get_columns("courses")}
            if "faculty_name" not in columns:
                conn.execute(text("ALTER TABLE courses ADD COLUMN faculty_name VARCHAR(255)"))
            if "department_name" not in columns:
                conn.execute(text("ALTER TABLE courses ADD COLUMN department_name VARCHAR(255)"))
            conn.execute(text("""
                UPDATE courses
                SET faculty_name = unit_name
                WHERE (faculty_name IS NULL OR faculty_name = '')
                  AND unit_name IS NOT NULL AND unit_name <> ''
            """))
        if "playlists" in tables:
            playlist_columns = {c["name"] for c in inspector.get_columns("playlists")}
            if "is_available" not in playlist_columns:
                conn.execute(text("ALTER TABLE playlists ADD COLUMN is_available BOOLEAN NOT NULL DEFAULT TRUE"))
        if "qr_codes" in tables:
            qr_columns = {c["name"] for c in inspector.get_columns("qr_codes")}
            if "target_type" not in qr_columns:
                conn.execute(text("ALTER TABLE qr_codes ADD COLUMN target_type VARCHAR(16) NOT NULL DEFAULT 'video'"))
            if "playlist_id" not in qr_columns:
                conn.execute(text("ALTER TABLE qr_codes ADD COLUMN playlist_id INTEGER"))
            conn.execute(text("UPDATE qr_codes SET target_type = 'video' WHERE target_type IS NULL OR target_type = ''"))
        if "course_playlists" in tables:
            cp_columns = {c["name"] for c in inspector.get_columns("course_playlists")}
            if "active" not in cp_columns:
                conn.execute(text("ALTER TABLE course_playlists ADD COLUMN active BOOLEAN NOT NULL DEFAULT TRUE"))
        if "course_videos" in tables:
            cv_columns = {c["name"] for c in inspector.get_columns("course_videos")}
            if "manual_added" not in cv_columns:
                # Dữ liệu cũ được coi là gán thủ công để không vô tình bị loại bỏ khi nâng cấp.
                conn.execute(text("ALTER TABLE course_videos ADD COLUMN manual_added BOOLEAN NOT NULL DEFAULT TRUE"))
        if "class_groups" in tables:
            class_columns = {c["name"] for c in inspector.get_columns("class_groups")}
            if "active" not in class_columns:
                conn.execute(text("ALTER TABLE class_groups ADD COLUMN active BOOLEAN NOT NULL DEFAULT TRUE"))
        if "functional_test_runs" in tables:
            test_columns = {c["name"] for c in inspector.get_columns("functional_test_runs")}
            if "source" not in test_columns:
                conn.execute(text("ALTER TABLE functional_test_runs ADD COLUMN source VARCHAR(16) NOT NULL DEFAULT 'manual'"))
            # Cho phép ghi lỗi OAuth trước khi xác định được user. PostgreSQL hỗ trợ trực tiếp.
            if db.engine.dialect.name == "postgresql":
                conn.execute(text("ALTER TABLE functional_test_runs ALTER COLUMN owner_id DROP NOT NULL"))

def record_functional_test(case_code, case_name, passed, owner_id=None, note="", source="automatic"):
    """Ghi bằng chứng kiểm thử phát sinh từ hoạt động thật của hệ thống.

    Hàm chỉ thêm bản ghi vào session hiện tại; caller chủ động commit cùng giao dịch nghiệp vụ.
    """
    db.session.add(FunctionalTestRun(
        owner_id=owner_id,
        case_code=(case_code or "AUTO")[:64],
        case_name=(case_name or "Kiểm thử tự động")[:255],
        passed=bool(passed),
        source=(source or "automatic")[:16],
        note=(note or "")[:4000],
    ))


def record_webapp_experiment(owner_id, task_key, elapsed_seconds, operations_count=1, success=True, note="", processing_seconds=None):
    """Ghi phép đo Web App tự động; dữ liệu đối chứng thủ công vẫn do quản trị viên nhập."""
    db.session.add(ExperimentRun(
        owner_id=owner_id,
        task_key=(task_key or "WEBAPP")[:128],
        mode="webapp",
        operations_count=max(0, int(operations_count or 0)),
        elapsed_seconds=max(0.0, float(elapsed_seconds or 0)),
        system_processing_seconds=(float(processing_seconds) if processing_seconds is not None else None),
        success=bool(success),
        note=(note or "")[:4000],
    ))


def research_setting(key, default=""):
    row = ResearchSetting.query.filter_by(key=key).first()
    return row.value if row and row.value else default


def save_research_setting(key, value):
    row = ResearchSetting.query.filter_by(key=key).first()
    if not row:
        row = ResearchSetting(key=key)
        db.session.add(row)
    row.value = (value or "").strip()


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


def allocate_lecturer_code(user: User) -> str:
    """Cấp mã GV ổn định, không chứa họ tên, do quản trị viên chủ động cấp."""
    if user.lecturer_code:
        return user.lecturer_code
    if user.role != "lecturer":
        raise ValueError("Chỉ cấp mã GV cho tài khoản giảng viên.")
    base = f"GV{user.id:04d}"
    code = base
    n = 1
    while User.query.filter(User.lecturer_code == code, User.id != user.id).first():
        n += 1
        code = f"{base}-{n}"
    user.lecturer_code = code
    return code


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


def safe_filename(value: str, fallback: str = "ma_qr") -> str:
    """Tạo tên tệp an toàn nhưng GIỮ NGUYÊN tiếng Việt có dấu.

    Chỉ loại các ký tự không hợp lệ trong tên tệp Windows/macOS và ký tự điều khiển;
    không phiên âm/khử dấu. Nhờ đó tên tệp QR tải về đúng tên video YouTube.
    """
    value = unicodedata.normalize("NFC", (value or "").strip())
    value = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "_", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    return (value[:180] or fallback)




def assign_auto_course_code(course: Course) -> str:
    """Sinh mã học phần tự động, ổn định và không yêu cầu GV nhập.

    Dùng khóa chính của CSDL để mã không trùng ngay cả khi nhiều giảng viên thao tác
    đồng thời. Mã chỉ phục vụ nhận diện nội bộ; người dùng chủ yếu làm việc bằng tên học phần.
    """
    if not course.id:
        db.session.flush()
    course.code = f"HP{course.id:06d}"
    return course.code


def assign_auto_class_code(class_group: ClassGroup) -> str:
    """Sinh mã lớp tự động; GV chỉ cần nhập tên lớp."""
    if not class_group.id:
        db.session.flush()
    class_group.code = f"L{class_group.id:06d}"
    return class_group.code


def assign_auto_school_class_code(school_class: SchoolClass) -> str:
    """Sinh mã lớp dùng chung tự động; quản trị viên chỉ nhập tên lớp và giao GVCN."""
    if not school_class.id:
        db.session.flush()
    school_class.code = f"L{school_class.id:06d}"
    return school_class.code


def video_is_usable(video: Video | None) -> bool:
    return bool(video and video.is_available and video.embeddable is not False and video.privacy_status != "private")


def course_owned_by_user(course: Course, user: User) -> bool:
    return bool(user.role == "admin" or course.owner_id == user.id)


def visible_video_query(user: User):
    q = Video.query.join(YouTubeChannel)
    if user.role != "admin":
        q = q.filter(YouTubeChannel.user_id == user.id)
    return q


def visible_playlist_query(user: User):
    """Playlist có thể gán vào học phần của tài khoản đang đăng nhập.

    Chỉ lấy playlist do chính kênh YouTube của người dùng sở hữu và còn tồn tại.
    Playlist Uploads hệ thống của YouTube không đưa vào danh sách gán học phần.
    """
    q = Playlist.query.join(YouTubeChannel).filter(YouTubeChannel.user_id == user.id)
    q = q.filter(Playlist.is_available.is_(True))
    q = q.filter((YouTubeChannel.uploads_playlist_id.is_(None)) | (Playlist.youtube_playlist_id != YouTubeChannel.uploads_playlist_id))
    return q


def ensure_course_playlist_link(course: Course, playlist: Playlist, user: User):
    link = CoursePlaylist.query.filter_by(course_id=course.id, playlist_id=playlist.id).first()
    if link:
        was_reactivated = not link.active
        link.active = True
        if not link.added_by:
            link.added_by = user.id
        return link, was_reactivated
    link = CoursePlaylist(course_id=course.id, playlist_id=playlist.id, added_by=user.id, active=True)
    db.session.add(link)
    db.session.flush()
    return link, True


def create_qr_for_course_playlist(course: Course, playlist: Playlist, user: User, link: CoursePlaylist | None = None):
    link = link or CoursePlaylist.query.filter_by(course_id=course.id, playlist_id=playlist.id, active=True).first()
    if link and link.qr_id:
        existing = db.session.get(QrCode, link.qr_id)
        if existing and existing.active:
            existing.title = (playlist.title or "Playlist")[:255]
            existing.target_type = "playlist"
            existing.playlist_id = playlist.id
            return existing, False
    existing = (QrCode.query
                .filter_by(owner_id=user.id, course_id=course.id, playlist_id=playlist.id, active=True)
                .filter(QrCode.target_type == "playlist")
                .order_by(QrCode.created_at.desc())
                .first())
    if existing:
        if link and link.qr_id != existing.id:
            link.qr_id = existing.id
        existing.title = (playlist.title or "Playlist")[:255]
        return existing, False
    t0 = time.perf_counter()
    slug = secrets.token_urlsafe(8).replace("-", "").replace("_", "")[:12]
    qr = QrCode(
        owner_id=user.id, course_id=course.id, slug=slug,
        title=(playlist.title or "Playlist")[:255], target_type="playlist", playlist_id=playlist.id,
    )
    db.session.add(qr)
    db.session.flush()
    if link:
        link.qr_id = qr.id
    db.session.flush()
    qr.processing_seconds = round(time.perf_counter() - t0, 4)
    return qr, True


def active_qr_for_course_video(course_id: int, video_id: int, owner_id: int):
    return (QrCode.query
            .join(QrTargetHistory, QrTargetHistory.qr_id == QrCode.id)
            .filter(QrCode.course_id == course_id, QrCode.owner_id == owner_id, QrCode.active.is_(True),
                    QrTargetHistory.video_id == video_id, QrTargetHistory.active_to.is_(None))
            .order_by(QrCode.created_at.desc())
            .first())


def ensure_course_video_link(course: Course, video: Video, user: User, source_playlist_id=None, manual=True):
    """Bảo đảm video thuộc học phần.

    manual=True khi GV chọn video trực tiếp; manual=False khi video được kế thừa
    tự động từ một playlist đã gán cho học phần. Cờ này giúp bỏ playlist mà không
    làm mất những video GV vẫn muốn giữ riêng trong học phần.
    """
    link = CourseVideo.query.filter_by(course_id=course.id, video_id=video.id).first()
    if link:
        if manual:
            link.manual_added = True
        elif not link.source_playlist_id and source_playlist_id:
            link.source_playlist_id = source_playlist_id
        return link, False
    link = CourseVideo(
        course_id=course.id,
        video_id=video.id,
        added_by=user.id,
        source_playlist_id=source_playlist_id,
        manual_added=bool(manual),
    )
    db.session.add(link)
    db.session.flush()
    return link, True


def reconcile_course_videos_from_playlists(course: Course, user: User):
    """Đồng bộ danh sách video của học phần theo các playlist đang được gán.

    - Video mới xuất hiện trong bất kỳ playlist đã gán nào sẽ tự động được thêm.
    - Khi bỏ playlist hoặc video bị gỡ khỏi playlist, liên kết tự động sẽ bị bỏ nếu
      video không còn thuộc playlist nào khác của học phần và chưa từng được GV gán riêng.
    - QR video đã phát hành không bị xóa; chỉ liên kết video-học phần được điều chỉnh.
    """
    active_links = CoursePlaylist.query.filter_by(course_id=course.id, active=True).all()
    playlist_ids = [x.playlist_id for x in active_links if x.playlist_id]
    desired = {}  # video_id -> một playlist nguồn đại diện
    if playlist_ids:
        rows = (db.session.query(PlaylistVideo.video_id, PlaylistVideo.playlist_id)
                .filter(PlaylistVideo.playlist_id.in_(playlist_ids)).all())
        for video_id, playlist_id in rows:
            desired.setdefault(video_id, playlist_id)

    existing = {x.video_id: x for x in CourseVideo.query.filter_by(course_id=course.id).all()}
    added = removed = 0
    for video_id, playlist_id in desired.items():
        if video_id not in existing:
            video = db.session.get(Video, video_id)
            if video:
                ensure_course_video_link(course, video, user, source_playlist_id=playlist_id, manual=False)
                added += 1
        else:
            link = existing[video_id]
            if not link.source_playlist_id:
                link.source_playlist_id = playlist_id

    for video_id, link in list(existing.items()):
        if video_id not in desired and not bool(getattr(link, "manual_added", True)):
            db.session.delete(link)
            removed += 1

    db.session.flush()
    return added, removed


def set_playlist_courses(playlist: Playlist, selected_course_ids: set[int], user: User):
    """Đặt lại toàn bộ các học phần áp dụng cho một playlist theo lựa chọn hiện tại."""
    owned_courses = Course.query.filter_by(owner_id=user.id, active=True).all()
    owned_by_id = {c.id: c for c in owned_courses}
    selected_course_ids = {cid for cid in selected_course_ids if cid in owned_by_id}
    existing = {x.course_id: x for x in CoursePlaylist.query.filter_by(playlist_id=playlist.id).all()
                if x.course and x.course.owner_id == user.id}
    affected = set()
    activated = deactivated = 0

    for course_id, course in owned_by_id.items():
        link = existing.get(course_id)
        should_be_active = course_id in selected_course_ids
        if should_be_active:
            if link:
                if not link.active:
                    link.active = True
                    activated += 1
                if not link.added_by:
                    link.added_by = user.id
            else:
                db.session.add(CoursePlaylist(course_id=course_id, playlist_id=playlist.id, added_by=user.id, active=True))
                activated += 1
            affected.add(course_id)
        elif link and link.active:
            link.active = False
            deactivated += 1
            affected.add(course_id)

    db.session.flush()
    auto_added = auto_removed = 0
    for course_id in affected:
        course = owned_by_id[course_id]
        a, r = reconcile_course_videos_from_playlists(course, user)
        auto_added += a
        auto_removed += r
    return activated, deactivated, auto_added, auto_removed


def create_qr_for_course_video(course: Course, video: Video, user: User, link: CourseVideo | None = None):
    link = link or CourseVideo.query.filter_by(course_id=course.id, video_id=video.id).first()
    if link and link.qr_id:
        existing = db.session.get(QrCode, link.qr_id)
        if existing and existing.active:
            # Luôn đồng bộ tên mã QR theo đúng tên video YouTube, giữ nguyên tiếng Việt có dấu.
            existing.title = (video.title or "Video")[:255]
            return existing, False
    existing = active_qr_for_course_video(course.id, video.id, user.id)
    if existing:
        if link and link.qr_id != existing.id:
            link.qr_id = existing.id
        existing.title = (video.title or "Video")[:255]
        return existing, False
    t0 = time.perf_counter()
    slug = secrets.token_urlsafe(8).replace("-", "").replace("_", "")[:12]
    qr = QrCode(owner_id=user.id, course_id=course.id, slug=slug, title=(video.title or "Video")[:255])
    db.session.add(qr)
    db.session.flush()
    db.session.add(QrTargetHistory(qr_id=qr.id, video_id=video.id, changed_by=user.id))
    if link:
        link.qr_id = qr.id
    db.session.flush()
    qr.processing_seconds = round(time.perf_counter() - t0, 4)
    return qr, True


def generate_branded_qr(qr: QrCode):
    """Tao QR thuong hieu theo mau chinh thuc cua nha truong.

    Mau chot: ma den - nen trang, muc sua loi H, logo Truong Cao dang
    Son La dat giua tren mot dia trang nho. URL van la URL QR dong,
    vi vay co the doi video dich ma khong doi hinh QR da phat hanh.
    """
    builder = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_H,
        box_size=int(current_app.config.get("QR_BOX_SIZE", 14)),
        border=int(current_app.config.get("QR_BORDER", 4)),
    )
    builder.add_data(qr_public_url(qr))
    builder.make(fit=True)
    img = builder.make_image(
        fill_color=current_app.config.get("QR_FILL_COLOR", "#000000"),
        back_color=current_app.config.get("QR_BACKGROUND_COLOR", "#FFFFFF"),
    ).convert("RGBA")

    logo_path = os.path.join(
        current_app.static_folder,
        current_app.config.get("BRAND_LOGO", "branding/logo_truong.png"),
    )
    if os.path.exists(logo_path):
        logo = Image.open(logo_path).convert("RGBA")
        alpha_bbox = logo.getchannel("A").getbbox()
        if alpha_bbox:
            logo = logo.crop(alpha_bbox)

        logo_ratio = float(current_app.config.get("QR_LOGO_RATIO", 0.23))
        logo_side = max(48, int(img.size[0] * logo_ratio))
        logo.thumbnail((logo_side, logo_side), Image.Resampling.LANCZOS)

        # Vong trang bao quanh logo giup mau trung tam ro rang va tang do on dinh khi quet.
        pad_ratio = float(current_app.config.get("QR_LOGO_WHITE_PAD_RATIO", 0.012))
        pad = max(6, int(img.size[0] * pad_ratio))
        badge_side = max(logo.width, logo.height) + pad * 2
        badge = Image.new("RGBA", (badge_side, badge_side), (255, 255, 255, 0))
        from PIL import ImageDraw
        draw = ImageDraw.Draw(badge)
        draw.ellipse((0, 0, badge_side - 1, badge_side - 1), fill=(255, 255, 255, 255))
        lx = (badge_side - logo.width) // 2
        ly = (badge_side - logo.height) // 2
        badge.alpha_composite(logo, (lx, ly))

        x = (img.width - badge.width) // 2
        y = (img.height - badge.height) // 2
        img.alpha_composite(badge, (x, y))

    return img


def qr_download_name(qr: QrCode) -> str:
    # Tên tệp QR = đúng tên video hoặc playlist, giữ nguyên tiếng Việt có dấu.
    if qr.is_playlist:
        source_title = qr.playlist.title if qr.playlist and qr.playlist.title else qr.title
    else:
        target = qr.current_target
        source_title = target.video.title if target and target.video and target.video.title else qr.title
    return f"{safe_filename(source_title, qr.slug)}.png"


def register_routes(app):
    @app.errorhandler(403)
    def handle_forbidden(error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "khong_co_quyen_truy_cap"}), 403
        if current_user():
            flash("Bạn không có quyền truy cập chức năng này.", "warning")
            return redirect(url_for("index"))
        return redirect(url_for("login", next=request.path))

    @app.errorhandler(404)
    def handle_not_found(error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "khong_tim_thay_du_lieu"}), 404
        return render_template("http_error.html", title="Không tìm thấy trang", message="Trang hoặc dữ liệu bạn yêu cầu không tồn tại."), 404

    @app.context_processor
    def inject_globals():
        endpoint = request.endpoint or ""
        section_map = {
            "youtube_page": "youtube", "youtube_sync": "youtube", "youtube_websub_subscribe": "youtube",
            "videos_page": "videos", "assign_videos_to_course": "videos", "assign_playlists_from_library": "videos",
            "courses_page": "courses", "add_class": "courses", "set_course_school_classes": "courses", "update_course_info": "courses",
            "assign_playlists_to_course": "courses", "delete_course_playlist": "courses",
            "create_course_qrs_bulk": "courses", "create_course_playlist_qrs_bulk": "courses", "download_course_qrs": "courses",
            "qr_page": "qr", "create_playlist_qr": "qr", "qr_retarget": "qr", "qr_png": "qr", "qr_download_all": "qr", "delete_all_qrs": "qr",
            "analytics": "analytics", "export_scans": "analytics", "export_watch": "analytics",
            "classes_page": "classes", "create_school_class": "classes", "assign_homeroom_teacher": "classes",
            "upload_class_students": "classes", "add_class_student": "classes", "change_student_status": "classes",
            "research_page": "research",
            "error_logs_page": "errors",
            "data_management": "data_admin",
            "update_display_name": "", "reset_lecturer_data": "",
            "backup_zip": "data_admin",
            "restore_backup": "data_admin",
        }
        return {
            "me": current_user(),
            "active_section": section_map.get(endpoint, ""),
            "heartbeat_seconds": current_app.config["HEARTBEAT_SECONDS"],
            "completion_threshold": current_app.config["COMPLETION_THRESHOLD"],
            "app_name": current_app.config["APP_NAME"],
            "app_tagline": current_app.config["APP_TAGLINE"],
            "school_name": current_app.config["SCHOOL_NAME"],
            "authors": current_app.config["AUTHORS"],
            "brand_logo": current_app.config["BRAND_LOGO"],
            "support_email": sorted(current_app.config["ADMIN_EMAILS"])[0] if current_app.config["ADMIN_EMAILS"] else "",
            "has_homeroom_classes": bool(current_user() and (current_user().role == "admin" or SchoolClass.query.filter_by(homeroom_teacher_id=current_user().id, active=True).first())),
        }

    @app.get("/health")
    def health():
        try:
            db.session.execute(text("SELECT 1"))
            return jsonify({"status": "ok", "database": "ok"})
        except Exception as exc:
            return jsonify({"status": "error", "detail": str(exc)}), 500

    @app.get("/privacy")
    def privacy_policy():
        return render_template("privacy.html")

    @app.get("/")
    def index():
        user = current_user()
        if not user:
            return render_template("landing.html")
        videos = visible_video_query(user).count()
        qrs = QrCode.query.filter_by(owner_id=user.id, active=True).count() if user.role != "admin" else QrCode.query.filter_by(active=True).count()
        courses = Course.query.filter_by(owner_id=user.id, active=True).count() if user.role != "admin" else Course.query.filter_by(active=True).count()

        # Giao diện thống kê chỉ đánh giá hoạt động quét/xem của sinh viên.
        scan_q = ScanLog.query.join(QrCode, ScanLog.qr_id == QrCode.id).filter(ScanLog.role == "SV")
        watch_q = WatchSession.query.join(QrCode, WatchSession.qr_id == QrCode.id).filter(WatchSession.role == "SV")
        if user.role != "admin":
            scan_q = scan_q.filter(QrCode.owner_id == user.id)
            watch_q = watch_q.filter(QrCode.owner_id == user.id)
        scans = scan_q.count()
        watch = watch_q.count()
        completed = watch_q.filter(WatchSession.completed.is_(True)).count()
        completion_rate = round(100 * completed / watch, 1) if watch else 0
        recent_scans = scan_q.order_by(ScanLog.scanned_at.desc()).limit(10).all()
        lecturer_count = User.query.filter_by(role="lecturer").count()
        class_count = SchoolClass.query.filter_by(active=True).count()
        lecturers_for_reset = User.query.filter_by(role="lecturer").order_by(User.name, User.email).all() if user.role == "admin" else []
        return render_template(
            "dashboard.html", videos=videos, courses=courses, qrs=qrs, scans=scans, watch=watch,
            completion_rate=completion_rate, recent_scans=recent_scans, lecturer_count=lecturer_count,
            class_count=class_count, lecturers_for_reset=lecturers_for_reset,
        )

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
                # Họ tên hiển thị có thể được người dùng hiệu chỉnh trong Web App;
                # không ghi đè lại bằng tên hồ sơ Google ở những lần đăng nhập sau.
                if not (user.name or "").strip():
                    user.name = info.get("name") or email
                user.google_sub = info.get("sub") or user.google_sub
                # Quyền quản trị chỉ dựa trên ADMIN_EMAILS hiện hành. Mọi tài khoản
                # Google khác luôn là giảng viên, kể cả trước đây từng được cấu hình admin.
                user.role = "admin" if email in current_app.config["ADMIN_EMAILS"] else "lecturer"
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
            record_functional_test(
                "AUTH_LOGIN", "Đăng nhập Google", True, owner_id=user.id,
                note=f"Đăng nhập thành công với vai trò {role_label(user.role)}."
            )
            db.session.commit()
            session["user_id"] = user.id
            session.permanent = True
            flash(f"Đăng nhập thành công với vai trò {role_label(user.role)}.", "success")
            after_login = session.pop("after_login", url_for("index"))
            if user.role != "admin" and after_login.startswith(("/research", "/admin/")):
                after_login = url_for("index")
            return redirect(after_login)
        except Exception as exc:
            db.session.rollback()
            db.session.add(ErrorLog(module="oauth", message="Đăng nhập Google thất bại", details=str(exc)))
            record_functional_test(
                "AUTH_LOGIN", "Đăng nhập Google", False, owner_id=None,
                note=f"OAuth thất bại: {exc}"
            )
            db.session.commit()
            flash(f"Đăng nhập thất bại: {exc}", "danger")
            return redirect(url_for("index"))

    @app.post("/profile/display-name")
    @login_required
    def update_display_name():
        user = current_user()
        display_name = re.sub(r"\s+", " ", (request.form.get("display_name") or "").strip())
        if len(display_name) < 2:
            flash("Vui lòng nhập họ và tên đầy đủ để hiển thị trên hệ thống.", "warning")
            return redirect(url_for("index"))
        user.name = display_name[:255]
        db.session.commit()
        flash("Đã cập nhật họ tên hiển thị.", "success")
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
        user = current_user()
        t0 = time.perf_counter()
        try:
            channels = sync_my_channel(user)
            # sync_my_channel đã đồng bộ uploads, các playlist do GV tạo và trạng thái
            # video hiện có; không gọi đối soát lần hai để tránh tiêu tốn hạn mức API.
            checked = sum(len(c.videos) for c in channels)
            elapsed = time.perf_counter() - t0
            record_functional_test(
                "YT_SYNC", "Đồng bộ kênh/video YouTube", True, owner_id=user.id,
                note=f"Đồng bộ {len(channels)} kênh; đối soát {checked} video."
            )
            db.session.commit()
            flash(f"Đã đồng bộ {len(channels)} kênh YouTube và kiểm tra trạng thái {checked} video.", "success")
        except Exception as exc:
            db.session.rollback()
            elapsed = time.perf_counter() - t0
            record_functional_test(
                "YT_SYNC", "Đồng bộ kênh/video YouTube", False, owner_id=user.id, note=str(exc)
            )
            db.session.commit()
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
            flash("Đã kích hoạt cập nhật tự động cho kênh YouTube. Hệ thống đang chờ xác nhận kết nối.", "success")
        except Exception as exc:
            flash("Không thể kích hoạt cập nhật tự động từ YouTube. Vui lòng kiểm tra nhật ký lỗi.", "danger")
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
                db.session.add(ErrorLog(module="websub", message="Nhận thông báo cập nhật nhưng đồng bộ video lỗi", details=str(exc)))
                db.session.commit()
        return "", 204

    @app.get("/videos")
    @login_required
    def videos_page():
        user = current_user()

        # --- Bộ lọc video ---
        q = visible_video_query(user)
        status = request.args.get("status", "").strip()
        assignment = request.args.get("assignment", "").strip()
        search = request.args.get("q", "").strip()
        playlist_filter_id = request.args.get("playlist_id", type=int)

        if status == "private":
            q = q.filter(Video.privacy_status == "private")
        elif status == "noembed":
            q = q.filter(Video.embeddable.is_(False))
        elif status == "unavailable":
            q = q.filter(Video.is_available.is_(False))
        elif status == "usable":
            q = q.filter(Video.is_available.is_(True), Video.privacy_status != "private", Video.embeddable.isnot(False))
        if search:
            q = q.filter(Video.title.ilike(f"%{search}%"))

        # Danh sách playlist của chính giảng viên để lọc video và gán học phần.
        available_playlists = visible_playlist_query(user).order_by(Playlist.title).all()
        allowed_playlist_ids = {p.id for p in available_playlists}
        if playlist_filter_id:
            if playlist_filter_id in allowed_playlist_ids:
                playlist_video_ids = db.session.query(PlaylistVideo.video_id).filter(PlaylistVideo.playlist_id == playlist_filter_id)
                q = q.filter(Video.id.in_(playlist_video_ids))
            else:
                # Không cho dùng ID playlist ngoài phạm vi tài khoản để lọc dữ liệu.
                q = q.filter(Video.id == -1)

        owned_course_ids = db.session.query(Course.id).filter(Course.owner_id == user.id, Course.active.is_(True))
        assigned_video_ids = db.session.query(CourseVideo.video_id).filter(CourseVideo.course_id.in_(owned_course_ids))
        if assignment == "unassigned":
            q = q.filter(~Video.id.in_(assigned_video_ids))
        elif assignment == "assigned":
            q = q.filter(Video.id.in_(assigned_video_ids))
        videos = q.order_by(Video.published_at.desc().nullslast(), Video.id.desc()).all()

        # --- Bộ lọc playlist ---
        playlist_search = request.args.get("p_q", "").strip()
        playlist_assignment = request.args.get("p_assignment", "").strip()
        pq = visible_playlist_query(user)
        if playlist_search:
            pq = pq.filter(Playlist.title.ilike(f"%{playlist_search}%"))
        assigned_playlist_ids = (
            db.session.query(CoursePlaylist.playlist_id)
            .filter(CoursePlaylist.course_id.in_(owned_course_ids), CoursePlaylist.active.is_(True))
        )
        if playlist_assignment == "unassigned":
            pq = pq.filter(~Playlist.id.in_(assigned_playlist_ids))
        elif playlist_assignment == "assigned":
            pq = pq.filter(Playlist.id.in_(assigned_playlist_ids))
        playlists = pq.order_by(Playlist.title).all()

        courses = Course.query.filter_by(owner_id=user.id, active=True).order_by(Course.name).all()
        return render_template(
            "videos.html",
            videos=videos,
            status=status,
            assignment=assignment,
            search=search,
            playlist_filter_id=playlist_filter_id,
            playlists=playlists,
            available_playlists=available_playlists,
            playlist_search=playlist_search,
            playlist_assignment=playlist_assignment,
            courses=courses,
        )

    @app.post("/videos/assign-course")
    @login_required
    def assign_videos_to_course():
        user = current_user()
        course_id = request.form.get("course_id", type=int)
        video_ids = request.form.getlist("video_ids")
        course = db.session.get(Course, course_id) if course_id else None
        if not course or not course.active or not course_owned_by_user(course, user):
            abort(403)
        if not video_ids:
            flash("Vui lòng chọn ít nhất một video để gán vào học phần.", "warning")
            return redirect(url_for("videos_page"))
        allowed_ids = {v.id for v in visible_video_query(user).filter(Video.id.in_([int(x) for x in video_ids if str(x).isdigit()])).all()}
        t0 = time.perf_counter()
        created = 0
        skipped = 0
        for video_id in allowed_ids:
            video = db.session.get(Video, video_id)
            _, was_created = ensure_course_video_link(course, video, user)
            if was_created:
                created += 1
            else:
                skipped += 1
        elapsed = time.perf_counter() - t0
        record_functional_test(
            "ASSIGN_COURSE", "Gán video vào học phần", True, owner_id=user.id,
            note=f"Học phần: {course.name}; gán mới {created}; bỏ qua {skipped}."
        )
        db.session.commit()
        flash(f"Đã gán {created} video vào học phần “{course.name}”. Bỏ qua {skipped} video đã được gán trước đó.", "success")
        return redirect(url_for("videos_page"))

    @app.post("/playlists/assign-course")
    @login_required
    def assign_playlists_from_library():
        """Gán playlist ngay tại Kho video học liệu để giảm thao tác cho giảng viên."""
        user = current_user()
        course_id = request.form.get("course_id", type=int)
        playlist_ids = [int(x) for x in request.form.getlist("playlist_ids") if str(x).isdigit()]
        course = db.session.get(Course, course_id) if course_id else None
        if not course or not course.active or not course_owned_by_user(course, user):
            abort(403)
        if not playlist_ids:
            flash("Vui lòng chọn ít nhất một playlist để gán vào học phần.", "warning")
            return redirect(url_for("videos_page"))

        allowed = {p.id: p for p in visible_playlist_query(user).filter(Playlist.id.in_(playlist_ids)).all()}
        created = 0
        skipped = 0
        for playlist_id in playlist_ids:
            playlist = allowed.get(playlist_id)
            if not playlist:
                continue
            _, was_created = ensure_course_playlist_link(course, playlist, user)
            if was_created:
                created += 1
            else:
                skipped += 1
        auto_added, auto_removed = reconcile_course_videos_from_playlists(course, user)
        record_functional_test(
            "ASSIGN_PLAYLIST", "Gán playlist vào học phần", bool(created or skipped), owner_id=user.id,
            note=f"Kho học liệu → {course.name}; playlist mới/khôi phục {created}; đã có {skipped}; video tự gán {auto_added}; video tự bỏ {auto_removed}."
        )
        db.session.commit()
        flash(
            f"Đã cập nhật playlist cho học phần “{course.name}”. Hệ thống tự gán thêm {auto_added} video thuộc playlist; không cần chọn lại từng video.",
            "success",
        )
        return redirect(url_for("videos_page") + "#playlists")

    @app.post("/playlists/<int:playlist_id>/set-courses")
    @login_required
    def set_playlist_course_assignments(playlist_id):
        """Lưu toàn bộ học phần áp dụng cho một playlist trong một thao tác.

        Danh sách học phần gửi lên là trạng thái cuối cùng: học phần được chọn sẽ
        nhận playlist và toàn bộ video của playlist; học phần bỏ chọn sẽ bỏ playlist
        và các video chỉ được kế thừa từ playlist đó.
        """
        user = current_user()
        playlist = db.session.get(Playlist, playlist_id) or abort(404)
        if playlist.channel.user_id != user.id:
            abort(403)
        selected_course_ids = {int(x) for x in request.form.getlist("course_ids") if str(x).isdigit()}
        activated, deactivated, auto_added, auto_removed = set_playlist_courses(playlist, selected_course_ids, user)
        record_functional_test(
            "SET_PLAYLIST_COURSES", "Thiết lập học phần cho playlist", True, owner_id=user.id,
            note=(f"Playlist: {playlist.title}; thêm/khôi phục học phần {activated}; bỏ học phần {deactivated}; "
                  f"video tự gán {auto_added}; video tự bỏ {auto_removed}."),
        )
        db.session.commit()
        flash(
            f"Đã lưu học phần cho playlist “{playlist.title}”. Video trong playlist được tự động đồng bộ vào các học phần đã chọn.",
            "success",
        )
        return redirect(url_for("videos_page") + "#playlists")

    @app.route("/courses", methods=["GET", "POST"])
    @login_required
    def courses_page():
        user = current_user()
        if request.method == "POST":
            name = request.form.get("course_name", "").strip()
            faculty = request.form.get("faculty_name", "").strip()
            department = request.form.get("department_name", "").strip()
            if not name or not faculty or not department:
                flash("Vui lòng nhập tên học phần, tên khoa và bộ môn quản lý học phần.", "warning")
            else:
                try:
                    # GV không phải tự đặt mã. Tạo mã tạm để lấy ID, sau đó đổi sang mã tự động ổn định.
                    course = Course(
                        owner_id=user.id,
                        code=f"TMP-{secrets.token_hex(8)}",
                        name=name,
                        unit_name=faculty,  # giữ tương thích dữ liệu/backup cũ
                        faculty_name=faculty,
                        department_name=department,
                    )
                    db.session.add(course)
                    db.session.flush()
                    assign_auto_course_code(course)
                    db.session.commit()
                    flash(f"Đã thêm học phần “{course.name}”. Mã học phần được hệ thống tự tạo.", "success")
                except Exception as exc:
                    db.session.rollback()
                    flash(f"Không thêm được học phần: {exc}", "danger")
            return redirect(url_for("courses_page"))
        all_owned_courses = Course.query.filter_by(owner_id=user.id).order_by(Course.created_at.desc()).all()
        courses = [c for c in all_owned_courses if c.active]
        # Không gợi ý tên học phần cũ. Tên khoa và bộ môn từng dùng vẫn được giữ
        # trong gợi ý để GV chọn lại nhanh, kể cả khi một học phần cũ đã được ẩn.
        faculty_options = sorted({((c.faculty_name or c.unit_name) or "").strip() for c in all_owned_courses if ((c.faculty_name or c.unit_name) or "").strip()}, key=str.casefold)
        department_options = sorted({(c.department_name or "").strip() for c in all_owned_courses if (c.department_name or "").strip()}, key=str.casefold)
        available_playlists = visible_playlist_query(user).order_by(Playlist.title).all()
        available_school_classes = SchoolClass.query.filter_by(active=True).order_by(SchoolClass.name).all()
        return render_template(
            "courses.html",
            courses=courses,
            faculty_options=faculty_options,
            department_options=department_options,
            available_playlists=available_playlists,
            available_school_classes=available_school_classes,
        )

    @app.post("/courses/<int:course_id>/info")
    @login_required
    def update_course_info(course_id):
        user = current_user()
        course = db.session.get(Course, course_id) or abort(404)
        if not course.active or not course_owned_by_user(course, user):
            abort(403)
        faculty = request.form.get("faculty_name", "").strip()
        department = request.form.get("department_name", "").strip()
        if not faculty or not department:
            flash("Vui lòng nhập đầy đủ tên khoa và bộ môn quản lý học phần.", "warning")
            return redirect(url_for("courses_page"))
        course.faculty_name = faculty
        course.department_name = department
        course.unit_name = faculty  # giữ tương thích với dữ liệu cũ
        db.session.commit()
        flash(f"Đã cập nhật khoa và bộ môn cho học phần “{course.name}”.", "success")
        return redirect(url_for("courses_page"))

    @app.post("/courses/<int:course_id>/playlists")
    @login_required
    def assign_playlists_to_course(course_id):
        user = current_user()
        course = db.session.get(Course, course_id) or abort(404)
        if not course.active or not course_owned_by_user(course, user):
            abort(403)
        playlist_ids = [int(x) for x in request.form.getlist("playlist_ids") if str(x).isdigit()]
        if not playlist_ids:
            flash("Vui lòng chọn ít nhất một playlist để gán vào học phần.", "warning")
            return redirect(url_for("courses_page"))
        allowed = {p.id: p for p in visible_playlist_query(user).filter(Playlist.id.in_(playlist_ids)).all()}
        created = 0
        skipped = 0
        for playlist_id in playlist_ids:
            playlist = allowed.get(playlist_id)
            if not playlist:
                continue
            _, was_created = ensure_course_playlist_link(course, playlist, user)
            if was_created:
                created += 1
            else:
                skipped += 1
        auto_added, auto_removed = reconcile_course_videos_from_playlists(course, user)
        record_functional_test(
            "ASSIGN_PLAYLIST", "Gán playlist vào học phần", bool(created or skipped), owner_id=user.id,
            note=f"Học phần: {course.name}; playlist mới/khôi phục {created}; đã có {skipped}; video tự gán {auto_added}; video tự bỏ {auto_removed}."
        )
        db.session.commit()
        flash(f"Đã gán playlist vào học phần “{course.name}” và tự động cập nhật các video thuộc playlist.", "success")
        return redirect(url_for("courses_page"))

    @app.post("/course-playlists/<int:link_id>/delete")
    @login_required
    def delete_course_playlist(link_id):
        user = current_user()
        link = db.session.get(CoursePlaylist, link_id) or abort(404)
        if not course_owned_by_user(link.course, user):
            abort(403)
        link.active = False
        auto_added, auto_removed = reconcile_course_videos_from_playlists(link.course, user)
        db.session.commit()
        flash(
            f"Đã bỏ playlist “{link.playlist.title}” khỏi học phần và tự động bỏ {auto_removed} video chỉ được kế thừa từ playlist này. Video đã gán riêng hoặc còn thuộc playlist khác vẫn được giữ.",
            "success",
        )
        return redirect(url_for("courses_page"))

    @app.post("/courses/<int:course_id>/school-classes")
    @login_required
    def set_course_school_classes(course_id):
        user = current_user()
        course = db.session.get(Course, course_id) or abort(404)
        if not course.active or not course_owned_by_user(course, user):
            abort(403)
        selected_ids = {int(x) for x in request.form.getlist("school_class_ids") if str(x).isdigit()}
        valid_ids = {c.id for c in SchoolClass.query.filter(SchoolClass.id.in_(selected_ids), SchoolClass.active.is_(True)).all()} if selected_ids else set()
        existing = {link.school_class_id: link for link in CourseClass.query.filter_by(course_id=course.id).all()}
        for class_id in valid_ids:
            link = existing.get(class_id)
            if link:
                link.active = True
                link.added_by = link.added_by or user.id
            else:
                db.session.add(CourseClass(course_id=course.id, school_class_id=class_id, added_by=user.id, active=True))
        for class_id, link in existing.items():
            if class_id not in valid_ids:
                link.active = False
        db.session.commit()
        flash(f"Đã cập nhật lớp áp dụng cho học phần “{course.name}”.", "success")
        return redirect(url_for("courses_page"))

    @app.post("/courses/<int:course_id>/classes")
    @login_required
    def add_class(course_id):
        course = db.session.get(Course, course_id) or abort(404)
        user = current_user()
        if user.role != "admin" and course.owner_id != user.id:
            abort(403)
        if not course.active:
            abort(404)
        name = request.form.get("class_name", "").strip()
        if not name:
            flash("Vui lòng nhập tên lớp.", "warning")
            return redirect(url_for("courses_page"))
        try:
            class_group = ClassGroup(
                course_id=course.id,
                code=f"TMP-{secrets.token_hex(8)}",
                name=name,
            )
            db.session.add(class_group)
            db.session.flush()
            assign_auto_class_code(class_group)
            db.session.commit()
            flash(f"Đã thêm lớp “{class_group.name}”. Mã lớp được hệ thống tự tạo.", "success")
        except Exception as exc:
            db.session.rollback()
            flash(f"Không thêm được lớp: {exc}", "danger")
        return redirect(url_for("courses_page"))

    @app.post("/courses/<int:course_id>/delete")
    @login_required
    def delete_course(course_id):
        """Ẩn học phần khỏi danh sách sử dụng nhưng giữ dữ liệu lịch sử.

        Không xóa cứng vì ScanLog/WatchSession/QR là minh chứng nghiên cứu. Các mã QR
        đã phát hành vẫn được giữ nguyên và có thể được xóa riêng nếu giảng viên muốn.
        """
        user = current_user()
        course = db.session.get(Course, course_id) or abort(404)
        if not course_owned_by_user(course, user):
            abort(403)
        course.active = False
        for cls in course.classes:
            if hasattr(cls, "active"):
                cls.active = False
        for link in course.playlist_links:
            link.active = False
        for link in course.school_class_links:
            link.active = False
        db.session.commit()
        flash(
            f"Đã xóa học phần “{course.name}” khỏi danh sách sử dụng. Dữ liệu lịch sử và mã QR đã phát hành được giữ lại để không mất minh chứng.",
            "success",
        )
        return redirect(url_for("courses_page"))

    @app.post("/classes/<int:class_id>/delete")
    @login_required
    def delete_class(class_id):
        user = current_user()
        class_group = db.session.get(ClassGroup, class_id) or abort(404)
        if not course_owned_by_user(class_group.course, user):
            abort(403)
        class_group.active = False
        db.session.commit()
        flash(
            f"Đã xóa lớp “{class_group.name}” khỏi danh sách. Dữ liệu quét/xem đã ghi trước đó vẫn được giữ nguyên.",
            "success",
        )
        return redirect(url_for("courses_page"))

    @app.post("/courses/<int:course_id>/qr/bulk")
    @login_required
    def create_course_qrs_bulk(course_id):
        user = current_user()
        course = db.session.get(Course, course_id) or abort(404)
        if not course.active or not course_owned_by_user(course, user):
            abort(403)
        links = CourseVideo.query.filter_by(course_id=course.id).order_by(CourseVideo.id).all()
        t0 = time.perf_counter()
        created = 0
        existing = 0
        skipped = 0
        total_processing = 0.0
        for link in links:
            video = link.video
            if not video_is_usable(video):
                skipped += 1
                continue
            qr, was_created = create_qr_for_course_video(course, video, user, link)
            if was_created:
                created += 1
                total_processing += qr.processing_seconds or 0.0
            else:
                existing += 1
        elapsed = time.perf_counter() - t0
        passed = bool(created or existing or not links)
        record_functional_test(
            "QR_BULK", "Tạo mã QR hàng loạt", passed, owner_id=user.id,
            note=f"Học phần: {course.name}; mới {created}; đã có {existing}; bỏ qua {skipped}."
        )
        record_webapp_experiment(
            user.id, "TAO_QR_HANG_LOAT", elapsed, operations_count=1, success=passed,
            note=f"{len(links)} video; mới {created}; đã có {existing}; bỏ qua {skipped}",
            processing_seconds=(total_processing / created if created else None),
        )
        db.session.commit()
        flash(
            f"Tạo mã QR hoàn tất: {created} mã mới, {existing} video đã có mã, {skipped} video chưa đủ điều kiện sử dụng.",
            "success" if created or existing else "warning",
        )
        # Khi tạo mã từ trang Quản lý mã QR động, giữ người dùng ở chính trang đó.
        # Khi tạo từ trang Học phần, quay lại trang Học phần như trước.
        return_to = request.form.get("return_to", "courses").strip().lower()
        return redirect(url_for("qr_page" if return_to == "qr" else "courses_page"))

    @app.post("/courses/<int:course_id>/playlist-qr/bulk")
    @login_required
    def create_course_playlist_qrs_bulk(course_id):
        user = current_user()
        course = db.session.get(Course, course_id) or abort(404)
        if not course.active or not course_owned_by_user(course, user):
            abort(403)
        links = CoursePlaylist.query.filter_by(course_id=course.id, active=True).order_by(CoursePlaylist.id).all()
        t0 = time.perf_counter()
        created = 0
        existing = 0
        skipped = 0
        total_processing = 0.0
        for link in links:
            playlist = link.playlist
            if not playlist or not playlist.is_available:
                skipped += 1
                continue
            qr, was_created = create_qr_for_course_playlist(course, playlist, user, link)
            if was_created:
                created += 1
                total_processing += qr.processing_seconds or 0.0
            else:
                existing += 1
        elapsed = time.perf_counter() - t0
        passed = bool(created or existing or not links)
        record_functional_test(
            "QR_PLAYLIST_BULK", "Tạo mã QR hàng loạt cho playlist", passed, owner_id=user.id,
            note=f"Học phần: {course.name}; mới {created}; đã có {existing}; bỏ qua {skipped}."
        )
        # QR cho nhiều playlist thuộc cùng nhóm nhiệm vụ đối chứng tạo QR hàng loạt.
        record_webapp_experiment(
            user.id, "TAO_QR_HANG_LOAT", elapsed, operations_count=1, success=passed,
            note=f"Playlist học phần {course.name}: tổng {len(links)}; mới {created}; đã có {existing}; bỏ qua {skipped}",
            processing_seconds=(total_processing / created if created else None),
        )
        db.session.commit()
        flash(
            f"Tạo QR playlist hoàn tất: {created} mã mới, {existing} playlist đã có mã, {skipped} playlist không còn khả dụng.",
            "success" if created or existing else "warning",
        )
        return_to = request.form.get("return_to", "courses").strip().lower()
        return redirect(url_for("qr_page" if return_to == "qr" else "courses_page"))

    @app.get("/courses/<int:course_id>/qr.zip")
    @login_required
    def download_course_qrs(course_id):
        user = current_user()
        course = db.session.get(Course, course_id) or abort(404)
        if not course_owned_by_user(course, user):
            abort(403)
        qrs = []
        seen = set()
        for link in CourseVideo.query.filter_by(course_id=course.id).filter(CourseVideo.qr_id.isnot(None)).all():
            if link.qr and link.qr.active and link.qr.id not in seen:
                qrs.append(link.qr); seen.add(link.qr.id)
        for link in CoursePlaylist.query.filter_by(course_id=course.id, active=True).filter(CoursePlaylist.qr_id.isnot(None)).all():
            if link.qr and link.qr.active and link.qr.id not in seen:
                qrs.append(link.qr); seen.add(link.qr.id)
        bio = io.BytesIO()
        used_names = set()
        with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
            for qr in qrs:
                img = generate_branded_qr(qr)
                png = io.BytesIO()
                img.save(png, format="PNG")
                name = qr_download_name(qr)
                if name in used_names:
                    stem, ext = os.path.splitext(name)
                    name = f"{stem}_{qr.slug}{ext}"
                used_names.add(name)
                zf.writestr(name, png.getvalue())
        bio.seek(0)
        filename = f"Ma_QR_{safe_filename(course.code)}.zip"
        return send_file(bio, mimetype="application/zip", as_attachment=True, download_name=filename)


    @app.route("/qr", methods=["GET", "POST"])
    @login_required
    def qr_page():
        user = current_user()
        if request.method == "POST":
            action_started = time.perf_counter()
            video_id = request.form.get("video_id", type=int)
            course_id = request.form.get("course_id", type=int)
            video = visible_video_query(user).filter(Video.id == video_id).first() if video_id else None
            course = db.session.get(Course, course_id) if course_id else None
            if not video or not video_is_usable(video):
                flash("Vui lòng chọn một video có thể sử dụng.", "warning")
                return redirect(url_for("qr_page"))
            if course and not course_owned_by_user(course, user):
                abort(403)
            # Tên mã QR luôn đúng bằng tên video YouTube, giữ nguyên tiếng Việt có dấu.
            title = (video.title or "Video")[:255]
            if course:
                link, _ = ensure_course_video_link(course, video, user)
                qr, was_created = create_qr_for_course_video(course, video, user, link)
                qr.title = title
                elapsed = time.perf_counter() - action_started
                record_functional_test(
                    "QR_SINGLE", "Tạo một mã QR", True, owner_id=user.id,
                    note=f"Video: {video.title}; học phần: {course.name}; tạo mới: {was_created}."
                )
                record_webapp_experiment(
                    user.id, "TAO_QR_RIENG", elapsed, operations_count=1, success=True,
                    note=f"Video: {video.title}; tạo mới: {was_created}",
                    processing_seconds=(qr.processing_seconds if was_created else 0.0),
                )
                db.session.commit()
                if was_created:
                    flash("Đã tạo mã QR động thành công.", "success")
                else:
                    flash("Video này đã có mã QR trong học phần; hệ thống không tạo trùng.", "info")
            else:
                t0 = time.perf_counter()
                slug = secrets.token_urlsafe(8).replace("-", "").replace("_", "")[:12]
                qr = QrCode(owner_id=user.id, course_id=None, slug=slug, title=title, target_type="video")
                db.session.add(qr)
                db.session.flush()
                db.session.add(QrTargetHistory(qr_id=qr.id, video_id=video.id, changed_by=user.id))
                qr.processing_seconds = round(time.perf_counter() - t0, 4)
                elapsed = time.perf_counter() - action_started
                record_functional_test(
                    "QR_SINGLE", "Tạo một mã QR", True, owner_id=user.id, note=f"Video: {video.title}; không gắn học phần."
                )
                record_webapp_experiment(
                    user.id, "TAO_QR_RIENG", elapsed, operations_count=1, success=True,
                    note=f"Video: {video.title}; không gắn học phần", processing_seconds=qr.processing_seconds
                )
                db.session.commit()
                flash("Đã tạo mã QR động thành công.", "success")
            return redirect(url_for("qr_page"))

        qrs = QrCode.query.filter_by(owner_id=user.id, active=True).order_by(QrCode.created_at.desc()).all()
        # Đồng bộ tên QR theo đúng tiêu đề nguồn hiện tại: video hoặc playlist.
        title_changed = False
        for existing_qr in qrs:
            if existing_qr.is_playlist:
                if existing_qr.playlist and existing_qr.playlist.title:
                    exact_title = existing_qr.playlist.title[:255]
                else:
                    exact_title = existing_qr.title
            else:
                target = existing_qr.current_target
                exact_title = target.video.title[:255] if target and target.video and target.video.title else existing_qr.title
            if existing_qr.title != exact_title:
                existing_qr.title = exact_title
                title_changed = True
        if title_changed:
            db.session.commit()

        videos = visible_video_query(user).filter(
            Video.is_available.is_(True), Video.privacy_status != "private", Video.embeddable.isnot(False)
        ).order_by(Video.title).all()
        courses = Course.query.filter_by(owner_id=user.id, active=True).order_by(Course.name).all()
        course_stats = []
        playlist_stats = []
        course_playlist_options = []
        for course in courses:
            links = CourseVideo.query.filter_by(course_id=course.id).all()
            total = len(links)
            has_qr = sum(1 for link in links if link.qr_id and link.qr and link.qr.active)
            usable_missing = sum(1 for link in links if not link.qr_id and video_is_usable(link.video))
            needs_retarget = sum(
                1 for link in links
                if link.qr_id and link.qr and link.qr.active and not video_is_usable(active_video_for_qr(link.qr))
            )
            course_stats.append({
                "course": course, "total": total, "has_qr": has_qr,
                "missing": usable_missing, "needs_retarget": needs_retarget,
            })

            plinks = CoursePlaylist.query.filter_by(course_id=course.id, active=True).all()
            p_total = len(plinks)
            p_has_qr = sum(1 for link in plinks if link.qr_id and link.qr and link.qr.active)
            p_missing = sum(1 for link in plinks if (not link.qr_id or not link.qr or not link.qr.active) and link.playlist and link.playlist.is_available)
            p_unavailable = sum(1 for link in plinks if not link.playlist or not link.playlist.is_available)
            playlist_stats.append({
                "course": course, "total": p_total, "has_qr": p_has_qr,
                "missing": p_missing, "unavailable": p_unavailable,
                "names": [link.playlist.title for link in plinks if link.playlist],
            })
            for link in plinks:
                if link.playlist and link.playlist.is_available:
                    course_playlist_options.append(link)
        return render_template(
            "qr.html", qrs=qrs, videos=videos, courses=courses, course_stats=course_stats,
            playlist_stats=playlist_stats, course_playlist_options=course_playlist_options,
        )

    @app.post("/qr/playlist")
    @login_required
    def create_playlist_qr():
        user = current_user()
        link_id = request.form.get("course_playlist_id", type=int)
        link = db.session.get(CoursePlaylist, link_id) if link_id else None
        if not link or not link.active or not link.course.active or not course_owned_by_user(link.course, user):
            abort(403)
        if not link.playlist or not link.playlist.is_available:
            flash("Playlist hiện không còn khả dụng trên YouTube. Hãy đồng bộ lại kênh hoặc chọn playlist khác.", "warning")
            return redirect(url_for("qr_page"))
        qr, was_created = create_qr_for_course_playlist(link.course, link.playlist, user, link)
        record_functional_test(
            "QR_PLAYLIST_SINGLE", "Tạo mã QR cho một playlist", True, owner_id=user.id,
            note=f"Học phần: {link.course.name}; playlist: {link.playlist.title}; tạo mới: {was_created}."
        )
        db.session.commit()
        flash("Đã tạo mã QR playlist thành công." if was_created else "Playlist này đã có mã QR trong học phần; hệ thống không tạo trùng.", "success" if was_created else "info")
        return redirect(url_for("qr_page"))


    @app.post("/qr/<int:qr_id>/retarget")
    @login_required
    def qr_retarget(qr_id):
        qr = db.session.get(QrCode, qr_id) or abort(404)
        user = current_user()
        if user.role != "admin" and qr.owner_id != user.id:
            abort(403)
        if not qr.active:
            abort(404)
        if qr.is_playlist:
            flash("Mã QR playlist tự cập nhật theo nội dung playlist sau mỗi lần đồng bộ YouTube; không đổi video đích theo cách này.", "info")
            return redirect(url_for("qr_page"))
        video_id = request.form.get("video_id", type=int)
        video = visible_video_query(user).filter(Video.id == video_id).first() if video_id else None
        if not video:
            abort(403)
        if not video_is_usable(video):
            flash("Video mới chưa đủ điều kiện sử dụng.", "warning")
            return redirect(url_for("qr_page"))
        linked = CourseVideo.query.filter_by(qr_id=qr.id).first()
        if linked and linked.video_id != video.id:
            duplicate = CourseVideo.query.filter_by(course_id=linked.course_id, video_id=video.id).first()
            if duplicate and duplicate.id != linked.id:
                if duplicate.qr_id and duplicate.qr_id != qr.id:
                    flash("Video mới đã có một mã QR khác trong cùng học phần; không thể tạo liên kết trùng.", "warning")
                    return redirect(url_for("qr_page"))
                db.session.delete(duplicate)
                db.session.flush()
            linked.video_id = video.id
        now = utcnow()
        old = qr.current_target
        if old:
            old.active_to = now
        db.session.add(QrTargetHistory(qr_id=qr.id, video_id=video.id, active_from=now, changed_by=user.id))
        qr.title = (video.title or qr.title)[:255]
        record_functional_test(
            "QR_RETARGET", "Đổi video đích của mã QR", True, owner_id=user.id,
            note=f"QR {qr.slug}; video mới: {video.title}."
        )
        db.session.commit()
        flash("Đã đổi video đích. Mã QR và đường dẫn không thay đổi.", "success")
        return redirect(url_for("qr_page"))

    @app.post("/qr/<int:qr_id>/delete")
    @login_required
    def delete_qr(qr_id):
        """Ngừng sử dụng một QR nhưng giữ log/lịch sử để phục vụ nghiên cứu."""
        qr = db.session.get(QrCode, qr_id) or abort(404)
        user = current_user()
        if user.role != "admin" and qr.owner_id != user.id:
            abort(403)
        if not qr.active:
            flash("Mã QR này đã được xóa khỏi danh sách sử dụng.", "info")
            return redirect(url_for("qr_page"))
        qr.active = False
        # Gỡ liên kết hiện hành để video trong học phần có thể tạo một QR mới nếu cần.
        for link in CourseVideo.query.filter_by(qr_id=qr.id).all():
            link.qr_id = None
        for link in CoursePlaylist.query.filter_by(qr_id=qr.id).all():
            link.qr_id = None
        db.session.commit()
        flash(
            f"Đã xóa mã QR “{qr.title}” khỏi danh sách sử dụng. Lịch sử quét/xem trước đây vẫn được giữ nguyên.",
            "success",
        )
        return redirect(url_for("qr_page"))

    @app.post("/qr/delete-all")
    @login_required
    def delete_all_qrs():
        user = current_user()
        qrs = QrCode.query.filter_by(owner_id=user.id, active=True).all()
        if not qrs:
            flash("Không có mã QR nào để xóa.", "info")
            return redirect(url_for("qr_page"))
        qr_ids = [q.id for q in qrs]
        for q in qrs:
            q.active = False
        if qr_ids:
            for link in CourseVideo.query.filter(CourseVideo.qr_id.in_(qr_ids)).all():
                link.qr_id = None
            for link in CoursePlaylist.query.filter(CoursePlaylist.qr_id.in_(qr_ids)).all():
                link.qr_id = None
        db.session.commit()
        flash(f"Đã xóa {len(qrs)} mã QR khỏi danh sách sử dụng. Lịch sử quét/xem trước đây vẫn được giữ lại.", "success")
        return redirect(url_for("qr_page"))

    @app.get("/qr/<int:qr_id>/png")
    @login_required
    def qr_png(qr_id):
        qr = db.session.get(QrCode, qr_id) or abort(404)
        user = current_user()
        if user.role != "admin" and qr.owner_id != user.id:
            abort(403)
        if not qr.active:
            abort(404)
        img = generate_branded_qr(qr)
        bio = io.BytesIO()
        img.save(bio, format="PNG")
        bio.seek(0)
        return send_file(bio, mimetype="image/png", as_attachment=True, download_name=qr_download_name(qr))

    @app.get("/qr/download-all.zip")
    @login_required
    def qr_download_all():
        user = current_user()
        qrs = QrCode.query.filter_by(active=True).all() if user.role == "admin" else QrCode.query.filter_by(owner_id=user.id, active=True).all()
        bio = io.BytesIO()
        used_names = set()
        with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
            for q in qrs:
                img = generate_branded_qr(q)
                png = io.BytesIO()
                img.save(png, format="PNG")
                name = qr_download_name(q)
                if name in used_names:
                    stem, ext = os.path.splitext(name)
                    name = f"{stem}_{q.slug}{ext}"
                used_names.add(name)
                zf.writestr(name, png.getvalue())
        bio.seek(0)
        return send_file(bio, mimetype="application/zip", as_attachment=True, download_name="Ma_QR_hoc_lieu.zip")

    @app.get("/q/<slug>")
    def public_qr(slug):
        qr = QrCode.query.filter_by(slug=slug, active=True).first_or_404()
        signed_in_user = current_user()

        # "Mở thử" dành cho GV/Quản trị viên đã đăng nhập: bỏ qua màn hình nhận diện
        # và không ghi lượt quét/thời lượng xem vào dữ liệu thực nghiệm.
        preview_mode = bool(
            request.args.get("preview") == "1"
            and signed_in_user
            and (signed_in_user.role == "admin" or qr.owner_id == signed_in_user.id)
        )
        tracking_enabled = not preview_mode

        if preview_mode:
            pcode = signed_in_user.lecturer_code or "XEM-THU"
            role = "GV"
            class_code = None
            viewer_identity = "Chế độ xem thử"
        elif signed_in_user and signed_in_user.role == "lecturer":
            # GV đăng nhập không phải nhập lại mã. Mã GV do quản trị viên cấp và
            # được dùng thống nhất trong dữ liệu thực nghiệm khi GV thực sự quét QR.
            if not signed_in_user.lecturer_code:
                return render_template(
                    "viewer_error.html", qr=qr,
                    message=("Tài khoản giảng viên chưa được quản trị viên cấp Mã GV. "
                             "Hãy liên hệ quản trị viên để được cấp mã. Nếu chỉ cần kiểm tra học liệu, "
                             "hãy dùng nút “Mở thử” trong giao diện Mã QR động."),
                ), 403
            pcode = signed_in_user.lecturer_code
            role = "GV"
            class_code = None
            viewer_identity = pcode
            session["participant_code"] = pcode
            session["participant_role"] = "GV"
            session["participant_class_code"] = ""
        elif signed_in_user and signed_in_user.role == "admin":
            # Quản trị viên kiểm tra QR nhưng không tạo dữ liệu người học giả.
            pcode = "QUAN-TRI"
            role = "GV"
            class_code = None
            viewer_identity = "Quản trị viên"
            tracking_enabled = False
        else:
            # Sinh viên không đăng nhập hệ thống quản trị. Chỉ nhập mã sinh viên do Nhà trường cấp;
            # hệ thống tự xác định lớp theo dữ liệu GVCN và thời điểm quét.
            session_code = session.get("participant_code") if session.get("participant_role") == "SV" else None
            if session_code:
                _, resolved_class, resolve_error = resolve_student_class_for_qr(session_code, qr)
                if resolve_error:
                    for key in ("participant_code", "participant_role", "participant_class_code"):
                        session.pop(key, None)
                    session_code = None
            if not session_code:
                session["identify_next"] = url_for("public_qr", slug=slug)
                session["identify_qr_slug"] = slug
                message = session.pop("identify_error", None)
                return render_template("identify.html", qr=qr, message=message)
            pcode = normalize_student_code(session_code)
            role = "SV"
            class_code = resolved_class.code
            viewer_identity = pcode
            session["participant_class_code"] = class_code

        if qr.is_playlist:
            playlist = qr.playlist
            links = PlaylistVideo.query.filter_by(playlist_id=playlist.id).order_by(PlaylistVideo.position.asc().nullslast(), PlaylistVideo.id).all() if playlist else []
            videos = [link.video for link in links if video_is_usable(link.video)]
            unavailable_count = max(0, len(links) - len(videos))
            success = bool(playlist and playlist.is_available and videos)
            if tracking_enabled:
                cutoff = utcnow() - timedelta(seconds=30)
                existing = ScanLog.query.filter(
                    ScanLog.participant_code == pcode,
                    ScanLog.qr_id == qr.id,
                    ScanLog.scanned_at >= cutoff,
                ).first()
                if not existing:
                    db.session.add(ScanLog(
                        participant_code=pcode, role=role, class_code=class_code,
                        course_id=qr.course_id, qr_id=qr.id, video_id=None, success=success,
                    ))
                    record_functional_test(
                        "QR_PLAYLIST_SCAN", "Quét mã QR playlist và mở học liệu", success, owner_id=qr.owner_id,
                        note=f"QR {qr.slug}; playlist: {playlist.title if playlist else 'không có'}; vai trò {role}."
                    )
                    db.session.commit()
            if not playlist:
                return render_template("viewer_error.html", qr=qr, message="Mã QR playlist chưa có playlist đích. Vui lòng liên hệ giảng viên phụ trách."), 404
            if not playlist.is_available:
                return render_template("viewer_error.html", qr=qr, message="Playlist đích đã bị xóa hoặc không còn khả dụng trên YouTube. Mã QR vẫn được giữ nguyên để giảng viên xử lý trong hệ thống."), 409
            if not videos:
                return render_template("viewer_error.html", qr=qr, message="Playlist hiện chưa có video nào đủ điều kiện phát trong trang học liệu. Vui lòng liên hệ giảng viên phụ trách."), 409
            return render_template(
                "playlist_viewer.html", qr=qr, playlist=playlist, videos=videos,
                unavailable_count=unavailable_count, preview_mode=preview_mode,
                tracking_enabled=tracking_enabled, viewer_identity=viewer_identity,
            )

        video = active_video_for_qr(qr)
        success = bool(video and video.is_available and video.embeddable is not False and video.privacy_status != "private")
        if tracking_enabled:
            cutoff = utcnow() - timedelta(seconds=30)
            existing = ScanLog.query.filter(
                ScanLog.participant_code == pcode,
                ScanLog.qr_id == qr.id,
                ScanLog.scanned_at >= cutoff,
            ).first()
            if not existing:
                db.session.add(ScanLog(
                    participant_code=pcode, role=role, class_code=class_code,
                    course_id=qr.course_id,
                    qr_id=qr.id,
                    video_id=video.id if video else None,
                    success=success,
                ))
                record_functional_test(
                    "QR_SCAN", "Quét mã QR và mở học liệu", success, owner_id=qr.owner_id,
                    note=f"QR {qr.slug}; vai trò {role}; trạng thái video: {video.status_label if video else 'không có video'}."
                )
                db.session.commit()

        if not video:
            return render_template("viewer_error.html", qr=qr, message="Mã QR chưa được gán video đích. Vui lòng liên hệ giảng viên phụ trách."), 404
        if not success:
            if not video.is_available:
                message = "Video đích đã bị xóa hoặc không còn tồn tại trên YouTube. Mã QR vẫn được giữ nguyên để giảng viên có thể thay video mới mà không phải phát hành lại mã QR."
            elif video.privacy_status == "private":
                message = "Video đích hiện đang ở chế độ riêng tư. Mã QR vẫn được giữ nguyên; giảng viên cần đổi quyền video hoặc cập nhật video thay thế."
            elif video.embeddable is False:
                message = "Video đích hiện không cho phép phát nhúng. Mã QR vẫn được giữ nguyên; giảng viên có thể cập nhật một video thay thế phù hợp."
            else:
                message = f"Video hiện không thể phát trong trang học liệu ({video.status_label}). Mã QR vẫn được giữ nguyên để có thể cập nhật video đích."
            return render_template("viewer_error.html", qr=qr, message=message), 409
        return render_template(
            "viewer.html", qr=qr, video=video, preview_mode=preview_mode,
            tracking_enabled=tracking_enabled, viewer_identity=viewer_identity,
        )


    @app.post("/identify")
    def identify():
        code = normalize_student_code(request.form.get("participant_code", ""))
        nxt = session.get("identify_next") or url_for("index")
        slug = session.get("identify_qr_slug")
        qr = QrCode.query.filter_by(slug=slug, active=True).first() if slug else None
        if not code:
            session["identify_error"] = "Vui lòng nhập mã sinh viên do Nhà trường cấp."
            return redirect(nxt)
        if not qr:
            session["identify_error"] = "Không xác định được mã QR đang truy cập. Vui lòng quét lại mã QR."
            return redirect(nxt)
        student, school_class, error = resolve_student_class_for_qr(code, qr)
        if error:
            session["identify_error"] = error
            return redirect(nxt)
        session["participant_code"] = student.student_code
        session["participant_role"] = "SV"
        session["participant_class_code"] = school_class.code
        session.pop("identify_qr_slug", None)
        session.pop("identify_error", None)
        session.pop("identify_next", None)
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
        if not session.get("participant_code"):
            return jsonify({"error": "missing_participant_or_video"}), 400

        if qr.is_playlist:
            video_id = data.get("video_id")
            try:
                video_id = int(video_id)
            except (TypeError, ValueError):
                return jsonify({"error": "missing_playlist_video"}), 400
            link = (PlaylistVideo.query
                    .filter_by(playlist_id=qr.playlist_id, video_id=video_id)
                    .first())
            video = link.video if link else None
            if not video_is_usable(video):
                return jsonify({"error": "invalid_playlist_video"}), 400
        else:
            video = active_video_for_qr(qr)
            if not video:
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
        scan_q = ScanLog.query.join(QrCode, ScanLog.qr_id == QrCode.id).filter(ScanLog.role == "SV")
        watch_q = WatchSession.query.join(QrCode, WatchSession.qr_id == QrCode.id).filter(WatchSession.role == "SV")
        if user.role != "admin":
            scan_q = scan_q.filter(QrCode.owner_id == user.id)
            watch_q = watch_q.filter(QrCode.owner_id == user.id)

        participant = request.args.get("participant", "").strip()
        class_code = request.args.get("class_code", "").strip()
        qr_slug = request.args.get("qr", "").strip()
        if participant:
            scan_q = scan_q.filter(ScanLog.participant_code.ilike(f"%{participant}%"))
            watch_q = watch_q.filter(WatchSession.participant_code.ilike(f"%{participant}%"))
        if class_code:
            scan_q = scan_q.filter(ScanLog.class_code == class_code)
            watch_q = watch_q.filter(WatchSession.class_code == class_code)
        if qr_slug:
            scan_q = scan_q.filter(QrCode.slug == qr_slug)
            watch_q = watch_q.filter(QrCode.slug == qr_slug)

        scans = scan_q.order_by(ScanLog.scanned_at.desc()).limit(500).all()
        watches = watch_q.order_by(WatchSession.started_at.desc()).limit(500).all()

        # Bộ lọc lớp dùng danh mục lớp dùng chung. Với giảng viên chỉ hiển thị lớp gắn với học phần mình phụ trách.
        if user.role == "admin":
            all_classes = SchoolClass.query.order_by(SchoolClass.name).all()
        else:
            all_classes = (SchoolClass.query.join(CourseClass, CourseClass.school_class_id == SchoolClass.id)
                           .join(Course, CourseClass.course_id == Course.id)
                           .filter(Course.owner_id == user.id)
                           .distinct().order_by(SchoolClass.name).all())
        class_options = [c for c in all_classes if c.active]
        class_name_map = {c.code: c.name for c in SchoolClass.query.all()}
        # Dữ liệu thử nghiệm cũ vẫn được hiển thị đúng tên nếu còn dùng mã lớp phiên bản trước.
        for legacy in ClassGroup.query.all():
            class_name_map.setdefault(legacy.code, legacy.name)

        day_q = db.session.query(func.date(ScanLog.scanned_at), func.count(ScanLog.id)).join(QrCode, ScanLog.qr_id == QrCode.id).filter(ScanLog.role == "SV")
        if user.role != "admin":
            day_q = day_q.filter(QrCode.owner_id == user.id)
        by_day = day_q.group_by(func.date(ScanLog.scanned_at)).order_by(func.date(ScanLog.scanned_at)).limit(30).all()
        chart_labels = [str(x[0]) for x in by_day]
        chart_values = [x[1] for x in by_day]
        return render_template("analytics.html", scans=scans, watches=watches,
                               chart_labels=chart_labels, chart_values=chart_values,
                               class_options=class_options, class_name_map=class_name_map)

    @app.get("/exports/scans.csv")
    @login_required
    def export_scans():
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(["Mã lượt quét", "Mã sinh viên", "Mã lớp", "Học phần", "Mã QR", "Mã video YouTube", "Thời gian quét", "Thành công"])
        user = current_user()
        q = ScanLog.query.join(QrCode, ScanLog.qr_id == QrCode.id).filter(ScanLog.role == "SV")
        if user.role != "admin":
            q = q.filter(QrCode.owner_id == user.id)
        for s in q.order_by(ScanLog.scanned_at).all():
            w.writerow([s.id, s.participant_code, s.class_code, s.course.code if s.course else "", s.qr.slug if s.qr else "", s.video.youtube_video_id if s.video else "", s.scanned_at.isoformat(), int(s.success)])
        return Response(out.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=scan_logs.csv"})

    @app.get("/exports/watch.csv")
    @login_required
    def export_watch():
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(["Mã phiên xem", "Mã sinh viên", "Mã lớp", "Mã QR", "Mã video YouTube", "Thời gian bắt đầu", "Thời lượng xem ước tính", "Vị trí xa nhất", "Thời lượng video", "Tỷ lệ hoàn thành", "Đã hoàn thành"])
        user = current_user()
        q = WatchSession.query.join(QrCode, WatchSession.qr_id == QrCode.id).filter(WatchSession.role == "SV")
        if user.role != "admin":
            q = q.filter(QrCode.owner_id == user.id)
        for s in q.order_by(WatchSession.started_at).all():
            w.writerow([s.session_key, s.participant_code, s.class_code, s.qr.slug if s.qr else "", s.video.youtube_video_id if s.video else "", s.started_at.isoformat(), round(s.estimated_watch_seconds, 2), round(s.max_position, 2), round(s.duration_seconds, 2), round(s.completion_percent, 2), int(s.completed)])
        return Response(out.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=watch_sessions.csv"})


    @app.get("/classes")
    @login_required
    def classes_page():
        user = current_user()
        if user.role == "admin":
            classes = SchoolClass.query.order_by(SchoolClass.name).all()
        else:
            classes = SchoolClass.query.filter_by(homeroom_teacher_id=user.id, active=True).order_by(SchoolClass.name).all()
            if not classes:
                flash("Tài khoản của bạn hiện chưa được giao chủ nhiệm lớp nào.", "info")
                return redirect(url_for("index"))
        today = utcnow().date()
        class_rows = []
        for school_class in classes:
            latest_by_student = {}
            for e in sorted(school_class.enrollments, key=lambda x: (x.started_on, x.id)):
                latest_by_student[e.student_id] = e
            student_rows = []
            for student_id, latest in latest_by_student.items():
                student = latest.student
                status_key, ref = student_current_status_in_class(student, school_class, today)
                student_rows.append({
                    "student": student,
                    "status_key": status_key,
                    "status_label": STUDENT_STATUS_LABELS.get(status_key, "Khác"),
                    "reference": ref,
                })
            student_rows.sort(key=lambda x: ((x["student"].full_name or "").casefold(), x["student"].student_code))
            class_rows.append({
                "class": school_class,
                "current_size": class_size_at(school_class, today),
                "student_rows": student_rows,
            })
        lecturers = User.query.filter_by(role="lecturer").order_by(User.name, User.email).all() if user.role == "admin" else []
        return render_template(
            "classes.html", class_rows=class_rows, lecturers=lecturers,
            status_labels=STUDENT_STATUS_LABELS, today=today,
        )

    @app.post("/admin/classes/create")
    @login_required
    def create_school_class():
        user = current_user()
        if user.role != "admin":
            flash("Bạn không có quyền thực hiện thao tác này.", "warning")
            return redirect(url_for("index"))
        name = (request.form.get("class_name") or "").strip()
        homeroom_id = request.form.get("homeroom_teacher_id", type=int)
        if not name:
            flash("Vui lòng nhập tên lớp.", "warning")
            return redirect(url_for("classes_page"))
        teacher = db.session.get(User, homeroom_id) if homeroom_id else None
        if teacher and teacher.role != "lecturer":
            teacher = None
        school_class = SchoolClass(code=f"TMP-{secrets.token_hex(8)}", name=name[:255], homeroom_teacher_id=teacher.id if teacher else None)
        db.session.add(school_class)
        db.session.flush()
        assign_auto_school_class_code(school_class)
        db.session.commit()
        flash(f"Đã tạo lớp “{name}”. Mã lớp {school_class.code} được hệ thống tự động tạo.", "success")
        return redirect(url_for("classes_page"))

    @app.post("/admin/classes/<int:class_id>/homeroom")
    @login_required
    def assign_homeroom_teacher(class_id):
        user = current_user()
        if user.role != "admin":
            flash("Bạn không có quyền thực hiện thao tác này.", "warning")
            return redirect(url_for("index"))
        school_class = db.session.get(SchoolClass, class_id) or abort(404)
        teacher_id = request.form.get("homeroom_teacher_id", type=int)
        teacher = db.session.get(User, teacher_id) if teacher_id else None
        if teacher and teacher.role != "lecturer":
            flash("Tài khoản được chọn không phải là giảng viên.", "warning")
            return redirect(url_for("classes_page"))
        school_class.homeroom_teacher_id = teacher.id if teacher else None
        db.session.commit()
        flash(f"Đã cập nhật giảng viên chủ nhiệm cho lớp “{school_class.name}”.", "success")
        return redirect(url_for("classes_page"))

    @app.get("/classes/student-template.xlsx")
    @login_required
    def student_excel_template():
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Danh sách sinh viên"
        ws.append(["Mã sinh viên", "Họ và tên"])
        ws.append(["MSSV001", "Nguyễn Văn A"])
        bio = io.BytesIO()
        wb.save(bio)
        bio.seek(0)
        return send_file(bio, as_attachment=True, download_name="Mau_danh_sach_sinh_vien.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    def read_students_from_excel(upload):
        from openpyxl import load_workbook
        wb = load_workbook(upload, read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            raise ValueError("Tệp Excel không có dữ liệu.")
        def clean_header(v):
            s = unicodedata.normalize("NFD", str(v or "").strip().lower())
            s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
            return re.sub(r"[^a-z0-9]+", " ", s).strip()
        headers = [clean_header(v) for v in rows[0]]
        code_idx = next((i for i,h in enumerate(headers) if h in {"ma sinh vien","ma sv","mssv","student code"}), None)
        name_idx = next((i for i,h in enumerate(headers) if h in {"ho va ten","ho ten","ten sinh vien","full name"}), None)
        if code_idx is None or name_idx is None:
            raise ValueError("Tệp Excel cần có hai cột: “Mã sinh viên” và “Họ và tên”.")
        result = []
        seen = set()
        for row in rows[1:]:
            code = normalize_student_code(row[code_idx] if code_idx < len(row) else "")
            name = str(row[name_idx] or "").strip() if name_idx < len(row) else ""
            if not code or not name or code in seen:
                continue
            seen.add(code)
            result.append((code, name[:255]))
        return result

    def add_student_to_school_class(school_class, code, name, effective_date):
        student = Student.query.filter_by(student_code=code).first()
        if not student:
            student = Student(student_code=code, full_name=name)
            db.session.add(student)
            db.session.flush()
        elif name and student.full_name != name:
            student.full_name = name
        for e in active_enrollments_for_student(student, effective_date):
            if e.school_class_id == school_class.id:
                return "already"
            return f"other:{e.school_class.name}"
        db.session.add(ClassEnrollment(school_class_id=school_class.id, student_id=student.id, started_on=effective_date))
        return "added"

    @app.post("/classes/<int:class_id>/students/upload")
    @login_required
    def upload_class_students(class_id):
        user = current_user()
        school_class = db.session.get(SchoolClass, class_id) or abort(404)
        if not can_manage_school_class(user, school_class):
            flash("Bạn chỉ được quản lý danh sách sinh viên của lớp mình chủ nhiệm.", "warning")
            return redirect(url_for("classes_page"))
        upload = request.files.get("student_file")
        effective_text = (request.form.get("effective_date") or "").strip()
        if not upload or not upload.filename:
            flash("Vui lòng chọn tệp Excel danh sách sinh viên.", "warning")
            return redirect(url_for("classes_page"))
        try:
            effective_date = date.fromisoformat(effective_text) if effective_text else utcnow().date()
            rows = read_students_from_excel(upload)
            added = already = conflict = 0
            conflicts = []
            for code, name in rows:
                result = add_student_to_school_class(school_class, code, name, effective_date)
                if result == "added": added += 1
                elif result == "already": already += 1
                else:
                    conflict += 1
                    conflicts.append(f"{code} đang thuộc {result.split(':',1)[1]}")
            db.session.commit()
            msg = f"Đã bổ sung {added} sinh viên vào lớp; {already} sinh viên đã có trong lớp"
            if conflict:
                msg += f"; {conflict} sinh viên chưa thêm do đang thuộc lớp khác"
            flash(msg + ".", "success" if added or already else "warning")
            if conflicts:
                flash("Cần kiểm tra: " + "; ".join(conflicts[:8]), "warning")
        except Exception as exc:
            db.session.rollback()
            flash(f"Không đọc được danh sách sinh viên: {exc}", "danger")
        return redirect(url_for("classes_page") + f"#lop-{school_class.id}")

    @app.post("/classes/<int:class_id>/students/add")
    @login_required
    def add_class_student(class_id):
        user = current_user()
        school_class = db.session.get(SchoolClass, class_id) or abort(404)
        if not can_manage_school_class(user, school_class):
            flash("Bạn chỉ được quản lý danh sách sinh viên của lớp mình chủ nhiệm.", "warning")
            return redirect(url_for("classes_page"))
        code = normalize_student_code(request.form.get("student_code", ""))
        name = (request.form.get("full_name") or "").strip()
        effective_text = (request.form.get("effective_date") or "").strip()
        if not code or not name:
            flash("Vui lòng nhập mã sinh viên và họ tên.", "warning")
            return redirect(url_for("classes_page") + f"#lop-{school_class.id}")
        try:
            effective_date = date.fromisoformat(effective_text) if effective_text else utcnow().date()
            result = add_student_to_school_class(school_class, code, name, effective_date)
            if result.startswith("other:"):
                raise ValueError(f"Sinh viên đang thuộc lớp {result.split(':',1)[1]} tại ngày hiệu lực. Hãy cập nhật trạng thái ở lớp cũ trước.")
            db.session.commit()
            flash("Đã bổ sung sinh viên vào lớp." if result == "added" else "Sinh viên đã có trong lớp ở thời điểm này.", "success" if result == "added" else "info")
        except Exception as exc:
            db.session.rollback()
            flash(f"Không thêm được sinh viên: {exc}", "danger")
        return redirect(url_for("classes_page") + f"#lop-{school_class.id}")

    @app.post("/classes/<int:class_id>/students/<int:student_id>/status")
    @login_required
    def change_student_status(class_id, student_id):
        user = current_user()
        school_class = db.session.get(SchoolClass, class_id) or abort(404)
        student = db.session.get(Student, student_id) or abort(404)
        if not can_manage_school_class(user, school_class):
            flash("Bạn chỉ được cập nhật sinh viên của lớp mình chủ nhiệm.", "warning")
            return redirect(url_for("classes_page"))
        status = (request.form.get("status") or "").strip()
        effective_text = (request.form.get("effective_date") or "").strip()
        note = (request.form.get("note") or "").strip()
        if status not in STUDENT_STATUS_LABELS:
            flash("Vui lòng chọn trạng thái hợp lệ.", "warning")
            return redirect(url_for("classes_page") + f"#lop-{school_class.id}")
        try:
            effective_date = date.fromisoformat(effective_text) if effective_text else utcnow().date()
            active_here = next((e for e in student.enrollments if e.school_class_id == school_class.id and enrollment_active_on(e, effective_date)), None)
            if status == "dang_hoc":
                if active_here:
                    flash("Sinh viên đang ở trạng thái Đang học trong lớp tại ngày này.", "info")
                    return redirect(url_for("classes_page") + f"#lop-{school_class.id}")
                for e in active_enrollments_for_student(student, effective_date):
                    if e.school_class_id != school_class.id:
                        raise ValueError(f"Sinh viên đang thuộc lớp {e.school_class.name} tại ngày hiệu lực.")
                db.session.add(ClassEnrollment(school_class_id=school_class.id, student_id=student.id, started_on=effective_date, note=note or None))
            else:
                if not active_here:
                    raise ValueError("Không tìm thấy khoảng thời gian sinh viên đang học tại lớp ở ngày hiệu lực đã chọn.")
                if effective_date < active_here.started_on:
                    raise ValueError("Ngày thay đổi không được trước ngày sinh viên bắt đầu vào lớp.")
                active_here.ended_on = effective_date
                active_here.end_status = status
                if note:
                    active_here.note = note
            db.session.commit()
            flash(f"Đã cập nhật trạng thái sinh viên thành “{STUDENT_STATUS_LABELS[status]}” từ ngày {effective_date.strftime('%d/%m/%Y')}.", "success")
        except Exception as exc:
            db.session.rollback()
            flash(f"Không cập nhật được trạng thái: {exc}", "danger")
        return redirect(url_for("classes_page") + f"#lop-{school_class.id}")

    @app.route("/research", methods=["GET", "POST"])
    @login_required
    def research_page():
        user = current_user()
        if user.role != "admin":
            flash("Bạn không có quyền truy cập chức năng này. Chức năng chỉ dành cho Quản trị viên.", "warning")
            return redirect(url_for("index"))

        if request.method == "POST":
            form_type = request.form.get("form_type")
            try:
                if form_type == "manual_experiment":
                    task_key = (request.form.get("task_key") or "").strip()
                    operations_count = int(request.form.get("operations_count") or 0)
                    elapsed_seconds = float(request.form.get("elapsed_seconds") or 0)
                    if task_key not in RESEARCH_COMPARISON_TASK_MAP:
                        raise ValueError("Vui lòng chọn một nhiệm vụ đối chứng trong danh mục chuẩn của hệ thống.")
                    if operations_count < 0 or elapsed_seconds < 0:
                        raise ValueError("Vui lòng nhập đầy đủ dữ liệu đối chứng thủ công.")
                    db.session.add(ExperimentRun(
                        owner_id=user.id,
                        task_key=task_key,
                        mode="manual",
                        operations_count=operations_count,
                        elapsed_seconds=elapsed_seconds,
                        system_processing_seconds=None,
                        success=request.form.get("success", "1") == "1",
                        note=(request.form.get("note") or "").strip(),
                    ))
                    flash("Đã lưu phép đo thủ công để làm dữ liệu đối chứng.", "success")
                elif form_type == "assign_lecturer_code":
                    lecturer_id = request.form.get("lecturer_id", type=int)
                    lecturer = db.session.get(User, lecturer_id) if lecturer_id else None
                    if not lecturer or lecturer.role != "lecturer":
                        raise ValueError("Không tìm thấy tài khoản giảng viên cần cấp mã.")
                    before = lecturer.lecturer_code
                    code = allocate_lecturer_code(lecturer)
                    if before:
                        flash(f"Giảng viên đã có mã {code}; hệ thống giữ nguyên mã để bảo toàn lịch sử thực nghiệm.", "info")
                    else:
                        flash(f"Đã cấp mã {code} cho giảng viên {lecturer.name or lecturer.email}.", "success")
                elif form_type == "survey_links":
                    save_research_setting("lecturer_form_url", request.form.get("lecturer_form_url"))
                    save_research_setting("student_form_url", request.form.get("student_form_url"))
                    save_research_setting("survey_results_url", request.form.get("survey_results_url"))
                    flash("Đã lưu liên kết Google Forms/Google Sheets.", "success")
                else:
                    raise ValueError("Biểu mẫu không hợp lệ.")
                db.session.commit()
            except Exception as exc:
                db.session.rollback()
                flash(f"Không lưu được dữ liệu: {exc}", "danger")
            return redirect(url_for("research_page"))

        metrics = acceptance_metrics(user)
        tests = FunctionalTestRun.query.filter_by(source="automatic").order_by(FunctionalTestRun.created_at.desc()).limit(200).all()
        tests_total = FunctionalTestRun.query.filter_by(source="automatic").count()
        tests_pass = FunctionalTestRun.query.filter_by(source="automatic", passed=True).count()
        tests_fail = max(0, tests_total - tests_pass)
        test_rate = round(100 * tests_pass / tests_total, 1) if tests_total else None

        experiments = ExperimentRun.query.order_by(ExperimentRun.created_at.desc()).limit(200).all()
        manual_runs = [x for x in experiments if x.mode == "manual"]
        webapp_runs = [x for x in experiments if x.mode == "webapp"]

        # Chỉ so sánh theo danh mục nhiệm vụ chuẩn. Nhờ vậy mã đối chứng thủ công
        # luôn trùng chính xác với mã Web App tự ghi và không phát sinh mã nhập sai.
        comparison_rows = []
        task_catalog = []
        for task in RESEARCH_COMPARISON_TASKS:
            key = task["key"]
            m = [x for x in manual_runs if x.task_key == key and x.success]
            w = [x for x in webapp_runs if x.task_key == key and x.success]
            m_ops = (sum(x.operations_count for x in m) / len(m)) if m else None
            w_ops = (sum(x.operations_count for x in w) / len(w)) if w else None
            m_time = (sum(x.elapsed_seconds for x in m) / len(m)) if m else None
            w_time = (sum(x.elapsed_seconds for x in w) / len(w)) if w else None
            reduction_ops = round(100 * (m_ops - w_ops) / m_ops, 1) if m_ops and w_ops is not None else None
            reduction_time = round(100 * (m_time - w_time) / m_time, 1) if m_time and w_time is not None else None
            comparison_rows.append({
                "task_key": key,
                "task_name": task["name"],
                "manual_task": task["manual_task"],
                "manual_ops": m_ops,
                "webapp_ops": w_ops,
                "manual_time": m_time,
                "webapp_time": w_time,
                "reduction_ops": reduction_ops,
                "reduction_time": reduction_time,
                "manual_count": len(m),
                "webapp_count": len(w),
            })
            if m and w:
                status = "Đủ dữ liệu để so sánh"
                status_class = "success"
            elif w and not m:
                status = "Cần đo quy trình thủ công"
                status_class = "warning"
            elif m and not w:
                status = "Cần thực hiện trên Web App"
                status_class = "warning"
            else:
                status = "Chưa có dữ liệu"
                status_class = "secondary"
            task_catalog.append({
                **task,
                "manual_count": len(m),
                "webapp_count": len(w),
                "status": status,
                "status_class": status_class,
            })

        survey_links = {
            "lecturer_form_url": research_setting("lecturer_form_url"),
            "student_form_url": research_setting("student_form_url"),
            "survey_results_url": research_setting("survey_results_url"),
        }
        lecturers = User.query.filter_by(role="lecturer").order_by(User.name, User.email).all()
        return render_template(
            "research.html",
            metrics=metrics,
            tests=tests,
            tests_total=tests_total,
            tests_pass=tests_pass,
            tests_fail=tests_fail,
            test_rate=test_rate,
            experiments=experiments,
            webapp_runs=webapp_runs,
            manual_runs=manual_runs,
            comparison_rows=comparison_rows,
            task_catalog=task_catalog,
            survey_links=survey_links,
            lecturers=lecturers,
        )

    def delete_lecturer_business_data(lecturer: User):
        """Xóa dữ liệu nghiệp vụ/thử nghiệm của một GV nhưng giữ tài khoản, họ tên, email, mã GV và quyền GVCN."""
        qr_ids = [x[0] for x in db.session.query(QrCode.id).filter(QrCode.owner_id == lecturer.id).all()]
        course_ids = [x[0] for x in db.session.query(Course.id).filter(Course.owner_id == lecturer.id).all()]
        channel_ids = [x[0] for x in db.session.query(YouTubeChannel.id).filter(YouTubeChannel.user_id == lecturer.id).all()]

        if qr_ids:
            watch_ids = [x[0] for x in db.session.query(WatchSession.id).filter(WatchSession.qr_id.in_(qr_ids)).all()]
            if watch_ids:
                WatchEvent.query.filter(WatchEvent.watch_session_id.in_(watch_ids)).delete(synchronize_session=False)
            WatchSession.query.filter(WatchSession.qr_id.in_(qr_ids)).delete(synchronize_session=False)
            ScanLog.query.filter(ScanLog.qr_id.in_(qr_ids)).delete(synchronize_session=False)
            QrTargetHistory.query.filter(QrTargetHistory.qr_id.in_(qr_ids)).delete(synchronize_session=False)

        if course_ids:
            Participant.query.filter(Participant.course_id.in_(course_ids)).delete(synchronize_session=False)
            CourseVideo.query.filter(CourseVideo.course_id.in_(course_ids)).delete(synchronize_session=False)
            CoursePlaylist.query.filter(CoursePlaylist.course_id.in_(course_ids)).delete(synchronize_session=False)
            CourseClass.query.filter(CourseClass.course_id.in_(course_ids)).delete(synchronize_session=False)
            ClassGroup.query.filter(ClassGroup.course_id.in_(course_ids)).delete(synchronize_session=False)

        QrCode.query.filter_by(owner_id=lecturer.id).delete(synchronize_session=False)
        Course.query.filter_by(owner_id=lecturer.id).delete(synchronize_session=False)

        if channel_ids:
            HubEvent.query.filter(HubEvent.channel_id.in_(channel_ids)).delete(synchronize_session=False)
            # HubSubscription/Playlist/Video/PlaylistVideo được xóa theo cascade khi xóa kênh.
        YouTubeChannel.query.filter_by(user_id=lecturer.id).delete(synchronize_session=False)

        ExperimentRun.query.filter_by(owner_id=lecturer.id).delete(synchronize_session=False)
        FunctionalTestRun.query.filter_by(owner_id=lecturer.id).delete(synchronize_session=False)
        SurveyResult.query.filter_by(owner_id=lecturer.id).delete(synchronize_session=False)

    @app.post("/admin/lecturers/<int:lecturer_id>/reset-data")
    @login_required
    def reset_lecturer_data(lecturer_id):
        user = current_user()
        if user.role != "admin":
            abort(403)
        lecturer = db.session.get(User, lecturer_id) or abort(404)
        if lecturer.role != "lecturer":
            flash("Chỉ có thể xóa dữ liệu của tài khoản giảng viên.", "warning")
            return redirect(url_for("index"))
        try:
            display = lecturer.name or lecturer.email
            delete_lecturer_business_data(lecturer)
            db.session.commit()
            flash(f"Đã xóa dữ liệu nghiệp vụ và thử nghiệm của giảng viên {display}. Tài khoản, mã GV và quyền GVCN được giữ lại.", "success")
        except Exception as exc:
            db.session.rollback()
            flash(f"Không thể xóa dữ liệu của giảng viên: {exc}", "danger")
        return redirect(url_for("index"))

    @app.post("/admin/reset-all-data")
    @login_required
    def reset_all_data():
        user = current_user()
        if user.role != "admin":
            abort(403)
        try:
            admin_id = user.id
            # Xóa toàn bộ dữ liệu nghiệp vụ/thử nghiệm nhưng giữ tài khoản + phiên OAuth
            # của chính quản trị viên đang thao tác để không phải đăng nhập lại.
            # Tất cả tài khoản GV bị xóa nên toàn bộ mã GV đã cấp cũng được làm mới từ đầu.
            keep_models = {User, OAuthAccount}
            for _, model in reversed(backup_table_specs()):
                if model in keep_models:
                    continue
                db.session.execute(model.__table__.delete())
            OAuthAccount.query.filter(OAuthAccount.user_id != admin_id).delete(synchronize_session=False)
            User.query.filter(User.id != admin_id).delete(synchronize_session=False)
            user.lecturer_code = None
            db.session.commit()
            session["user_id"] = admin_id
            session.permanent = True
            flash("Đã xóa toàn bộ dữ liệu đã lưu và toàn bộ mã GV đã cấp. Phiên quản trị hiện tại được giữ để bạn tiếp tục thiết lập hệ thống từ đầu.", "success")
            return redirect(url_for("index"))
        except Exception as exc:
            db.session.rollback()
            flash(f"Không thể xóa toàn bộ dữ liệu: {exc}", "danger")
            return redirect(url_for("index"))

    @app.route("/admin/data", methods=["GET", "POST"])
    @login_required
    def data_management():
        user = current_user()
        if user.role != "admin":
            abort(403)

        if request.method == "POST":
            upload = request.files.get("backup_file")
            confirm = (request.form.get("confirm") or "").strip()
            if not upload or not upload.filename:
                flash("Vui lòng chọn tệp sao lưu ZIP do chính hệ thống tạo.", "warning")
                return redirect(url_for("data_management"))
            if confirm != "KHÔI PHỤC":
                flash("Vui lòng nhập chính xác KHÔI PHỤC để xác nhận thao tác.", "warning")
                return redirect(url_for("data_management"))
            try:
                admin_email = user.email
                restore_from_zip(upload.stream)
                # Sau restore, user hiện tại có thể đã đổi ID hoặc không còn trong bộ dữ liệu khôi phục.
                restored_admin = User.query.filter_by(email=admin_email).first()
                record_functional_test(
                    "RESTORE", "Khôi phục dữ liệu từ bản sao lưu", True,
                    owner_id=(restored_admin.id if restored_admin else None), note=upload.filename or ""
                )
                db.session.commit()
                session.clear()
                flash("Khôi phục dữ liệu thành công. Vui lòng đăng nhập lại.", "success")
                return redirect(url_for("index"))
            except Exception as exc:
                db.session.rollback()
                db.session.add(ErrorLog(module="restore", message="Khôi phục bản sao lưu thất bại", details=str(exc)))
                record_functional_test("RESTORE", "Khôi phục dữ liệu từ bản sao lưu", False, owner_id=user.id, note=str(exc))
                db.session.commit()
                flash(f"Khôi phục thất bại: {exc}", "danger")
                return redirect(url_for("data_management"))

        summary = {
            "videos": Video.query.count(),
            "courses": Course.query.filter_by(active=True).count(),
            "qrs": QrCode.query.filter_by(active=True).count(),
            "scans": ScanLog.query.count(),
        }
        return render_template("data_management.html", summary=summary)

    @app.get("/admin/backup.zip")
    @login_required
    def backup_zip():
        user = current_user()
        if user.role != "admin":
            abort(403)
        try:
            bio = build_backup_zip()
            record_functional_test("BACKUP", "Tạo bản sao lưu ZIP", True, owner_id=user.id)
            db.session.commit()
            return send_file(bio, mimetype="application/zip", as_attachment=True, download_name=f"sao_luu_ma_qr_{utcnow().date().isoformat()}.zip")
        except Exception as exc:
            db.session.rollback()
            record_functional_test("BACKUP", "Tạo bản sao lưu ZIP", False, owner_id=user.id, note=str(exc))
            db.session.commit()
            raise

    @app.route("/admin/restore", methods=["GET", "POST"])
    @login_required
    def restore_backup():
        # Giữ tương thích với liên kết cũ; giao diện quản trị mới dùng /admin/data.
        if current_user().role != "admin":
            abort(403)
        if request.method == "POST":
            flash("Giao diện khôi phục đã được chuyển sang mục Sao lưu & khôi phục.", "info")
        return redirect(url_for("data_management"))

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



BACKUP_VERSION = "3.0"

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
        ("school_classes", SchoolClass),
        ("students", Student),
        ("class_enrollments", ClassEnrollment),
        ("course_classes", CourseClass),
        ("participants", Participant),
        ("qr_codes", QrCode),
        ("course_videos", CourseVideo),
        ("course_playlists", CoursePlaylist),
        ("qr_target_history", QrTargetHistory),
        ("scan_logs", ScanLog),
        ("watch_sessions", WatchSession),
        ("watch_events", WatchEvent),
        ("hub_subscriptions", HubSubscription),
        ("hub_events", HubEvent),
        ("error_logs", ErrorLog),
        ("experiment_runs", ExperimentRun),
        ("functional_test_runs", FunctionalTestRun),
        ("research_settings", ResearchSetting),
        ("survey_results", SurveyResult),
    ]

def build_backup_zip():
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
        manifest = {
            "product": current_app.config.get("APP_NAME", "TẠO MÃ QR TỰ ĐỘNG TỪ VIDEO YOUTUBE"),
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
        if manifest.get("backup_version") not in {"2.0", "2.1", BACKUP_VERSION}:
            raise ValueError("Phiên bản backup không tương thích.")
        payload = {}
        for name, model in backup_table_specs():
            fn = f"{name}.json"
            if fn not in names:
                # Các bảng bổ sung ở phiên bản sau là tùy chọn để backup cũ vẫn khôi phục được.
                if name in {"research_settings", "course_playlists", "school_classes", "students", "class_enrollments", "course_classes"}:
                    payload[name] = []
                    continue
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
                    if v is not None and isinstance(v, str):
                        if isinstance(col.type, DateTime):
                            v = datetime.fromisoformat(v.replace("Z", "+00:00"))
                        elif col.type.__class__.__name__ == "Date":
                            v = date.fromisoformat(v[:10])
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
    migrate_legacy_classes()

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
    """Tính chỉ tiêu nghiệm thu.

    Khi người dùng là quản trị viên, số liệu được tổng hợp trên toàn hệ thống để
    phản ánh thực nghiệm của nhiều giảng viên/bộ môn. Nhánh người dùng thường vẫn
    được giữ để hàm có thể tái sử dụng khi cần.
    """
    scan_q = ScanLog.query.join(QrCode, ScanLog.qr_id == QrCode.id)
    if user.role != "admin":
        scan_q = scan_q.filter(QrCode.owner_id == user.id)
    scans_total = scan_q.count()
    scans_success = scan_q.filter(ScanLog.success.is_(True)).count()
    scan_rate = round(100 * scans_success / scans_total, 1) if scans_total else None

    tests_q = FunctionalTestRun.query.filter(FunctionalTestRun.source == "automatic")
    if user.role != "admin":
        tests_q = tests_q.filter(FunctionalTestRun.owner_id == user.id)
    tests_total = tests_q.count()
    tests_pass = tests_q.filter(FunctionalTestRun.passed.is_(True)).count()
    test_rate = round(100 * tests_pass / tests_total, 1) if tests_total else None

    exp_q = ExperimentRun.query if user.role == "admin" else ExperimentRun.query.filter_by(owner_id=user.id)
    comparison_keys = list(RESEARCH_COMPARISON_TASK_MAP.keys())
    manual = exp_q.filter(ExperimentRun.mode == "manual", ExperimentRun.success.is_(True), ExperimentRun.task_key.in_(comparison_keys)).all()
    webapp = exp_q.filter(ExperimentRun.mode == "webapp", ExperimentRun.success.is_(True), ExperimentRun.task_key.in_(comparison_keys)).all()
    # Chỉ so sánh các nhiệm vụ có dữ liệu ở CẢ hai phía để tránh trộn các công việc khác nhau.
    matched_keys = {x.task_key for x in manual} & {x.task_key for x in webapp}
    manual_matched = [x for x in manual if x.task_key in matched_keys]
    webapp_matched = [x for x in webapp if x.task_key in matched_keys]
    manual_ops = sum(x.operations_count for x in manual_matched) / len(manual_matched) if manual_matched else None
    app_ops = sum(x.operations_count for x in webapp_matched) / len(webapp_matched) if webapp_matched else None
    manual_time = sum(x.elapsed_seconds for x in manual_matched) / len(manual_matched) if manual_matched else None
    app_time = sum(x.elapsed_seconds for x in webapp_matched) / len(webapp_matched) if webapp_matched else None

    qr_perf_q = QrCode.query.filter(QrCode.processing_seconds.isnot(None))
    if user.role != "admin":
        qr_perf_q = qr_perf_q.filter(QrCode.owner_id == user.id)
    qr_perf = [q.processing_seconds for q in qr_perf_q.all() if q.processing_seconds is not None]
    processing_values = qr_perf or [x.system_processing_seconds for x in webapp if x.system_processing_seconds is not None]
    avg_processing = sum(processing_values) / len(processing_values) if processing_values else None

    reduction_ops = round(100 * (manual_ops - app_ops) / manual_ops, 1) if manual_ops and app_ops is not None else None
    reduction_time = round(100 * (manual_time - app_time) / manual_time, 1) if manual_time and app_time is not None else None

    # Khảo sát được thu bằng Google Forms và thống kê trong Google Sheets để tránh nhập tay từng phiếu.
    # Web App chỉ liên kết tới nguồn khảo sát; hai chỉ tiêu hài lòng được đánh giá từ Sheets khi nghiệm thu.
    lecturer_sat = None
    student_sat = None

    participant_base = db.session.query(ScanLog.participant_code).join(QrCode, ScanLog.qr_id == QrCode.id)
    if user.role != "admin":
        participant_base = participant_base.filter(QrCode.owner_id == user.id)
    gv_count = participant_base.filter(ScanLog.role == "GV").distinct().count()
    sv_count = participant_base.filter(ScanLog.role == "SV").distinct().count()

    video_q = Video.query.join(YouTubeChannel)
    if user.role != "admin":
        video_q = video_q.filter(YouTubeChannel.user_id == user.id)

    course_q = Course.query.filter_by(active=True) if user.role == "admin" else Course.query.filter_by(owner_id=user.id, active=True)
    course_count = course_q.count()

    # Mỗi tổ hợp Khoa + Bộ môn được tính là một đơn vị tham gia thực nghiệm.
    # Nhờ vậy nhiều bộ môn trong cùng một khoa vẫn được ghi nhận riêng.
    unit_rows = course_q.with_entities(Course.faculty_name, Course.department_name, Course.unit_name).all()
    unit_keys = set()
    for faculty, department, legacy_unit in unit_rows:
        faculty = (faculty or legacy_unit or "").strip()
        department = (department or "").strip()
        if faculty or department:
            unit_keys.add((faculty.casefold(), department.casefold()))
    unit_count = len(unit_keys)

    return [
        metric("Tỷ lệ QR quét thành công", scan_rate, ">=", 98, "%"),
        metric("Thời gian xử lý hệ thống trung bình/video", round(avg_processing, 2) if avg_processing is not None else None, "<=", 5, " giây"),
        metric("Giảm số thao tác so với thủ công", reduction_ops, ">=", 30, "%"),
        metric("Giảm tổng thời gian so với thủ công", reduction_time, ">=", 30, "%"),
        metric("Tỷ lệ ca kiểm thử chức năng đạt", test_rate, ">=", 95, "%"),
        metric("Số học phần thực nghiệm", course_count, ">=", 3, ""),
        metric("Số đơn vị/khoa/bộ môn", unit_count, ">=", 2, ""),
        metric("Số giảng viên tham gia", gv_count, ">=", 5, ""),
        metric("Số sinh viên tham gia", sv_count, ">=", 60, ""),
        metric("Số video/tình huống kiểm thử", video_q.count(), ">=", 100, ""),
        metric("Mức hài lòng giảng viên", lecturer_sat, ">=", 80, "%", external=True),
        metric("Mức hài lòng sinh viên", student_sat, ">=", 80, "%", external=True),
    ]


def metric(name, value, op, target, suffix, external=False):
    passed = None
    if value is not None:
        passed = value >= target if op == ">=" else value <= target
    return {"name": name, "value": value, "op": op, "target": target, "suffix": suffix, "passed": passed, "external": external}


def serialize_model(obj):
    out = {}
    for col in obj.__table__.columns:
        value = getattr(obj, col.name)
        if hasattr(value, "isoformat"):
            value = value.isoformat()
        out[col.name] = value
    return out
