from __future__ import annotations

from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint, Index


db = SQLAlchemy()


def utcnow():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False, default="")
    google_sub = db.Column(db.String(255), unique=True, nullable=True)
    role = db.Column(db.String(32), nullable=False, default="lecturer")
    # Mã GV dùng cho nhận diện trong thực nghiệm/ghi log. Hệ thống tự cấp,
    # không thay thế tài khoản Google và không chứa họ tên.
    lecturer_code = db.Column(db.String(32), unique=True, nullable=True, index=True)
    # Phân nhóm chuyên môn phục vụ chỉ tiêu nghiệm thu: CNTT / khác CNTT.
    # Để trống khi quản trị viên chưa xác định.
    professional_group = db.Column(db.String(16), nullable=True)
    profile_completed = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True)


class OAuthAccount(db.Model):
    __tablename__ = "oauth_accounts"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    provider = db.Column(db.String(32), nullable=False, default="google")
    token_encrypted = db.Column(db.Text, nullable=False)
    scopes = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    user = db.relationship("User", backref=db.backref("oauth_account", uselist=False, cascade="all,delete"))


class YouTubeChannel(db.Model):
    __tablename__ = "youtube_channels"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    channel_id = db.Column(db.String(64), nullable=False)
    title = db.Column(db.String(255), nullable=False, default="")
    uploads_playlist_id = db.Column(db.String(128), nullable=True)
    thumbnail_url = db.Column(db.Text, nullable=True)
    last_synced_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    user = db.relationship("User", backref=db.backref("youtube_channels", cascade="all,delete"))
    __table_args__ = (UniqueConstraint("user_id", "channel_id", name="uq_user_channel"),)


class Playlist(db.Model):
    __tablename__ = "playlists"
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.Integer, db.ForeignKey("youtube_channels.id", ondelete="CASCADE"), nullable=False)
    youtube_playlist_id = db.Column(db.String(128), nullable=False, unique=True)
    title = db.Column(db.String(255), nullable=False, default="")
    description = db.Column(db.Text, nullable=True)
    privacy_status = db.Column(db.String(32), nullable=True)
    is_available = db.Column(db.Boolean, nullable=False, default=True, server_default="true")
    last_synced_at = db.Column(db.DateTime(timezone=True), nullable=True)
    channel = db.relationship("YouTubeChannel", backref=db.backref("playlists", cascade="all,delete"))


class Video(db.Model):
    __tablename__ = "videos"
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.Integer, db.ForeignKey("youtube_channels.id", ondelete="CASCADE"), nullable=False)
    youtube_video_id = db.Column(db.String(32), nullable=False, unique=True, index=True)
    title = db.Column(db.String(500), nullable=False, default="")
    description = db.Column(db.Text, nullable=True)
    published_at = db.Column(db.DateTime(timezone=True), nullable=True)
    privacy_status = db.Column(db.String(32), nullable=True)
    upload_status = db.Column(db.String(32), nullable=True)
    embeddable = db.Column(db.Boolean, nullable=True)
    is_available = db.Column(db.Boolean, nullable=False, default=True)
    duration_iso = db.Column(db.String(64), nullable=True)
    thumbnail_url = db.Column(db.Text, nullable=True)
    last_synced_at = db.Column(db.DateTime(timezone=True), nullable=True)
    channel = db.relationship("YouTubeChannel", backref=db.backref("videos", cascade="all,delete"))

    @property
    def status_label(self):
        if not self.is_available:
            return "Không truy cập"
        if self.privacy_status == "private":
            return "Riêng tư"
        if self.embeddable is False:
            return "Không cho nhúng"
        return self.privacy_status or self.upload_status or "Chưa rõ"


class PlaylistVideo(db.Model):
    __tablename__ = "playlist_videos"
    id = db.Column(db.Integer, primary_key=True)
    playlist_id = db.Column(db.Integer, db.ForeignKey("playlists.id", ondelete="CASCADE"), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    position = db.Column(db.Integer, nullable=True)
    playlist = db.relationship("Playlist", backref=db.backref("video_links", cascade="all,delete"))
    video = db.relationship("Video", backref=db.backref("playlist_links", cascade="all,delete"))
    __table_args__ = (UniqueConstraint("playlist_id", "video_id", name="uq_playlist_video"),)


class Course(db.Model):
    __tablename__ = "courses"
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    code = db.Column(db.String(64), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    # unit_name được giữ để tương thích dữ liệu/backup cũ. Từ v2.5,
    # faculty_name và department_name là hai thông tin nghiệp vụ riêng biệt.
    unit_name = db.Column(db.String(255), nullable=True)
    faculty_name = db.Column(db.String(255), nullable=True)
    department_name = db.Column(db.String(255), nullable=True)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    owner = db.relationship("User", backref=db.backref("courses", cascade="all,delete"))
    __table_args__ = (UniqueConstraint("owner_id", "code", name="uq_owner_course_code"),)


class CourseVideo(db.Model):
    __tablename__ = "course_videos"
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    qr_id = db.Column(db.Integer, db.ForeignKey("qr_codes.id", ondelete="SET NULL"), nullable=True, unique=True)
    added_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    source_playlist_id = db.Column(db.Integer, db.ForeignKey("playlists.id", ondelete="SET NULL"), nullable=True)
    # True nếu GV đã gán video trực tiếp; False nếu video được tự động kế thừa từ playlist.
    manual_added = db.Column(db.Boolean, nullable=False, default=True, server_default="true")
    added_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    course = db.relationship("Course", backref=db.backref("video_links", cascade="all,delete", order_by="CourseVideo.added_at"))
    video = db.relationship("Video", backref=db.backref("course_links", cascade="all,delete"))
    qr = db.relationship("QrCode", foreign_keys=[qr_id])
    adder = db.relationship("User", foreign_keys=[added_by])
    source_playlist = db.relationship("Playlist")
    __table_args__ = (UniqueConstraint("course_id", "video_id", name="uq_course_video"),)


class CoursePlaylist(db.Model):
    __tablename__ = "course_playlists"
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    playlist_id = db.Column(db.Integer, db.ForeignKey("playlists.id", ondelete="CASCADE"), nullable=False)
    qr_id = db.Column(db.Integer, db.ForeignKey("qr_codes.id", ondelete="SET NULL"), nullable=True, unique=True)
    added_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    active = db.Column(db.Boolean, nullable=False, default=True, server_default="true")
    added_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    course = db.relationship("Course", backref=db.backref("playlist_links", cascade="all,delete", order_by="CoursePlaylist.added_at"))
    playlist = db.relationship("Playlist", backref=db.backref("course_links", cascade="all,delete"))
    qr = db.relationship("QrCode", foreign_keys=[qr_id])
    adder = db.relationship("User", foreign_keys=[added_by])
    __table_args__ = (UniqueConstraint("course_id", "playlist_id", name="uq_course_playlist"),)


class ClassGroup(db.Model):
    __tablename__ = "class_groups"
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    code = db.Column(db.String(64), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    course = db.relationship("Course", backref=db.backref("classes", cascade="all,delete"))
    __table_args__ = (UniqueConstraint("course_id", "code", name="uq_course_class_code"),)


class SchoolClass(db.Model):
    """Danh mục lớp dùng chung toàn hệ thống, không gắn riêng với từng học phần."""
    __tablename__ = "school_classes"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64), unique=True, nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    homeroom_teacher_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    active = db.Column(db.Boolean, nullable=False, default=True, server_default="true")
    declared_size = db.Column(db.Integer, nullable=True)  # Chỉ là sĩ số GVCN khai báo, không thay danh sách SV thực tế.
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    homeroom_teacher = db.relationship("User", foreign_keys=[homeroom_teacher_id], backref=db.backref("homeroom_classes", lazy=True))


class Student(db.Model):
    """Sinh viên dùng mã do Nhà trường cấp làm mã định danh duy nhất."""
    __tablename__ = "students"
    id = db.Column(db.Integer, primary_key=True)
    student_code = db.Column(db.String(64), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(255), nullable=False, default="")
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)


class ClassEnrollment(db.Model):
    """Khoảng thời gian một sinh viên thuộc một lớp. ended_on là ngày trạng thái mới có hiệu lực."""
    __tablename__ = "class_enrollments"
    id = db.Column(db.Integer, primary_key=True)
    school_class_id = db.Column(db.Integer, db.ForeignKey("school_classes.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    started_on = db.Column(db.Date, nullable=False)
    ended_on = db.Column(db.Date, nullable=True)
    end_status = db.Column(db.String(32), nullable=True)
    note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    school_class = db.relationship("SchoolClass", backref=db.backref("enrollments", cascade="all,delete"))
    student = db.relationship("Student", backref=db.backref("enrollments", cascade="all,delete"))
    __table_args__ = (Index("ix_enrollment_class_student_dates", "school_class_id", "student_id", "started_on", "ended_on"),)


class CourseClass(db.Model):
    """Liên kết nhiều-nhiều giữa học phần và lớp dùng chung."""
    __tablename__ = "course_classes"
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    school_class_id = db.Column(db.Integer, db.ForeignKey("school_classes.id", ondelete="CASCADE"), nullable=False, index=True)
    added_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    active = db.Column(db.Boolean, nullable=False, default=True, server_default="true")
    added_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    course = db.relationship("Course", backref=db.backref("school_class_links", cascade="all,delete", order_by="CourseClass.added_at"))
    school_class = db.relationship("SchoolClass", backref=db.backref("course_links", cascade="all,delete"))
    adder = db.relationship("User", foreign_keys=[added_by])
    __table_args__ = (UniqueConstraint("course_id", "school_class_id", name="uq_course_school_class"),)


class Participant(db.Model):
    __tablename__ = "participants"
    id = db.Column(db.Integer, primary_key=True)
    participant_code = db.Column(db.String(128), nullable=False, index=True)
    role = db.Column(db.String(16), nullable=False, default="SV")
    class_code = db.Column(db.String(64), nullable=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    course = db.relationship("Course")
    __table_args__ = (UniqueConstraint("participant_code", "course_id", name="uq_participant_course"),)


class QrCode(db.Model):
    __tablename__ = "qr_codes"
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)
    slug = db.Column(db.String(64), unique=True, nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    target_type = db.Column(db.String(16), nullable=False, default="video", server_default="video")
    playlist_id = db.Column(db.Integer, db.ForeignKey("playlists.id", ondelete="SET NULL"), nullable=True)
    active = db.Column(db.Boolean, default=True, nullable=False)
    processing_seconds = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    owner = db.relationship("User", backref=db.backref("qr_codes", cascade="all,delete"))
    course = db.relationship("Course")
    playlist = db.relationship("Playlist", foreign_keys=[playlist_id])

    @property
    def is_playlist(self):
        return (self.target_type or "video") == "playlist" or self.playlist_id is not None

    @property
    def current_target(self):
        return QrTargetHistory.query.filter_by(qr_id=self.id, active_to=None).order_by(QrTargetHistory.active_from.desc()).first()


class QrTargetHistory(db.Model):
    __tablename__ = "qr_target_history"
    id = db.Column(db.Integer, primary_key=True)
    qr_id = db.Column(db.Integer, db.ForeignKey("qr_codes.id", ondelete="CASCADE"), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey("videos.id", ondelete="RESTRICT"), nullable=False)
    active_from = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    active_to = db.Column(db.DateTime(timezone=True), nullable=True)
    changed_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    qr = db.relationship("QrCode", backref=db.backref("target_history", cascade="all,delete", order_by="QrTargetHistory.active_from"))
    video = db.relationship("Video")
    changer = db.relationship("User")
    __table_args__ = (Index("ix_qr_target_current", "qr_id", "active_to"),)


class ScanLog(db.Model):
    __tablename__ = "scan_logs"
    id = db.Column(db.Integer, primary_key=True)
    participant_code = db.Column(db.String(128), nullable=False, index=True)
    role = db.Column(db.String(16), nullable=False)
    class_code = db.Column(db.String(64), nullable=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)
    qr_id = db.Column(db.Integer, db.ForeignKey("qr_codes.id", ondelete="SET NULL"), nullable=True)
    video_id = db.Column(db.Integer, db.ForeignKey("videos.id", ondelete="SET NULL"), nullable=True)
    scanned_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    success = db.Column(db.Boolean, default=True, nullable=False)
    course = db.relationship("Course")
    qr = db.relationship("QrCode")
    video = db.relationship("Video")


class WatchSession(db.Model):
    __tablename__ = "watch_sessions"
    id = db.Column(db.Integer, primary_key=True)
    session_key = db.Column(db.String(64), unique=True, nullable=False, index=True)
    participant_code = db.Column(db.String(128), nullable=False, index=True)
    role = db.Column(db.String(16), nullable=False)
    class_code = db.Column(db.String(64), nullable=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)
    qr_id = db.Column(db.Integer, db.ForeignKey("qr_codes.id", ondelete="SET NULL"), nullable=True)
    video_id = db.Column(db.Integer, db.ForeignKey("videos.id", ondelete="SET NULL"), nullable=True)
    started_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    last_event_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    ended_at = db.Column(db.DateTime(timezone=True), nullable=True)
    estimated_watch_seconds = db.Column(db.Float, default=0.0, nullable=False)
    max_position = db.Column(db.Float, default=0.0, nullable=False)
    duration_seconds = db.Column(db.Float, default=0.0, nullable=False)
    completion_percent = db.Column(db.Float, default=0.0, nullable=False)
    completed = db.Column(db.Boolean, default=False, nullable=False)
    last_state = db.Column(db.String(16), default="unstarted", nullable=False)
    last_position = db.Column(db.Float, default=0.0, nullable=False)
    course = db.relationship("Course")
    qr = db.relationship("QrCode")
    video = db.relationship("Video")


class WatchEvent(db.Model):
    __tablename__ = "watch_events"
    id = db.Column(db.Integer, primary_key=True)
    watch_session_id = db.Column(db.Integer, db.ForeignKey("watch_sessions.id", ondelete="CASCADE"), nullable=False)
    event_type = db.Column(db.String(24), nullable=False)
    player_state = db.Column(db.String(16), nullable=True)
    position = db.Column(db.Float, nullable=False, default=0.0)
    duration = db.Column(db.Float, nullable=False, default=0.0)
    counted_seconds = db.Column(db.Float, nullable=False, default=0.0)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    watch_session = db.relationship("WatchSession", backref=db.backref("events", cascade="all,delete"))


class HubSubscription(db.Model):
    __tablename__ = "hub_subscriptions"
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.Integer, db.ForeignKey("youtube_channels.id", ondelete="CASCADE"), unique=True, nullable=False)
    topic_url = db.Column(db.Text, nullable=False)
    callback_url = db.Column(db.Text, nullable=False)
    callback_secret = db.Column(db.String(128), nullable=False)
    verified = db.Column(db.Boolean, default=False, nullable=False)
    lease_seconds = db.Column(db.Integer, nullable=True)
    lease_expires_at = db.Column(db.DateTime(timezone=True), nullable=True)
    last_subscribed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    last_verified_at = db.Column(db.DateTime(timezone=True), nullable=True)
    channel = db.relationship("YouTubeChannel", backref=db.backref("hub_subscription", uselist=False, cascade="all,delete"))


class HubEvent(db.Model):
    __tablename__ = "hub_events"
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.Integer, db.ForeignKey("youtube_channels.id", ondelete="SET NULL"), nullable=True)
    youtube_video_id = db.Column(db.String(32), nullable=True)
    event_type = db.Column(db.String(32), nullable=False, default="notification")
    raw_payload = db.Column(db.Text, nullable=True)
    received_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    processed = db.Column(db.Boolean, default=False, nullable=False)
    channel = db.relationship("YouTubeChannel")


class ErrorLog(db.Model):
    __tablename__ = "error_logs"
    id = db.Column(db.Integer, primary_key=True)
    # module giữ lại để tương thích dữ liệu cũ/nội bộ; giao diện không hiển thị thuật ngữ kỹ thuật này.
    module = db.Column(db.String(64), nullable=False)
    action = db.Column(db.String(128), nullable=True)
    course_module = db.Column(db.String(255), nullable=True)
    message = db.Column(db.String(500), nullable=False)
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)


class ExperimentRun(db.Model):
    __tablename__ = "experiment_runs"
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    task_key = db.Column(db.String(128), nullable=False)
    mode = db.Column(db.String(16), nullable=False)  # manual | webapp
    operations_count = db.Column(db.Integer, nullable=False)
    elapsed_seconds = db.Column(db.Float, nullable=False)
    system_processing_seconds = db.Column(db.Float, nullable=True)
    success = db.Column(db.Boolean, default=True, nullable=False)
    note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    owner = db.relationship("User")


class FunctionalTestRun(db.Model):
    __tablename__ = "functional_test_runs"
    id = db.Column(db.Integer, primary_key=True)
    # owner_id có thể rỗng để ghi nhận cả lỗi OAuth xảy ra trước khi hệ thống xác định được người dùng.
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    case_code = db.Column(db.String(64), nullable=False)
    case_name = db.Column(db.String(255), nullable=False)
    passed = db.Column(db.Boolean, nullable=False)
    source = db.Column(db.String(16), nullable=False, default="automatic")
    note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    owner = db.relationship("User")




class ResearchSetting(db.Model):
    __tablename__ = "research_settings"
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), unique=True, nullable=False, index=True)
    value = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class SurveyResult(db.Model):
    __tablename__ = "survey_results"
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    respondent_type = db.Column(db.String(16), nullable=False)  # GV | SV
    respondent_code = db.Column(db.String(128), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1..5
    note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    owner = db.relationship("User")
