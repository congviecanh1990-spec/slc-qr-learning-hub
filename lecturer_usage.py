"""Bảng chỉ số theo giảng viên cho trang Thống kê khai thác.

Phạm vi phân công hiện hành: chủ môn hoặc giảng viên được giao riêng lớp.
Tất cả số SV là số người duy nhất, không phải tổng lượt quét/video.
Hoàn thành = đã xem đủ các video gắn với TẤT CẢ học phần được giao
cho SV trong phạm vi giảng viên; học phần chưa gắn video không tính hoàn thành.
"""
from collections import defaultdict
from datetime import date
from sqlalchemy import and_, or_
from models import (
    db, User, Course, CourseClass, SchoolClass, ClassEnrollment, Student,
    QrCode, ScanLog, WatchSession, CourseVideo, CoursePlaylist, PlaylistVideo,
)


def lecturer_usage_rows(user, threshold: float, today: date):
    """Lọc quyền trước mọi phép tổng hợp; không cộng trùng người học hoặc lớp."""
    is_admin = user.role == "admin"
    # Quản trị viên cũng có thể trực tiếp giảng dạy; không loại họ khỏi báo cáo.
    # Tài khoản đăng nhập là GV chỉ được xem dòng của chính mình.
    lecturers = (User.query.filter(User.role.in_(("lecturer", "admin")))
                 if is_admin else User.query.filter(User.id == user.id))
    people = lecturers.order_by(User.name, User.email).all()
    if not people:
        return []
    ids = {person.id for person in people}

    courses = Course.query.filter(Course.active.is_(True)).all()
    courses_by_id = {c.id: c for c in courses}
    links = (db.session.query(CourseClass, SchoolClass)
             .join(SchoolClass, SchoolClass.id == CourseClass.school_class_id)
             .filter(CourseClass.active.is_(True), SchoolClass.active.is_(True)).all())

    course_ids = defaultdict(set)
    class_ids = defaultdict(set)
    scope = defaultdict(set)  # (course_id, class_id) cho mỗi giảng viên
    for link, school_class in links:
        course = courses_by_id.get(link.course_id)
        if course is None:
            continue
        lecturer_id = link.assigned_lecturer_id or course.owner_id
        if lecturer_id not in ids:
            continue
        scope[lecturer_id].add((course.id, school_class.id))
        course_ids[lecturer_id].add(course.id)
        class_ids[lecturer_id].add(school_class.id)

    # Môn chưa gán lớp vẫn thuộc GV chủ môn. Nếu toàn bộ lớp được
    # bàn giao cho người khác thì không tính là môn đang dạy của chủ cũ.
    courses_with_classes = {link.course_id for link, _ in links}
    for course in courses:
        if course.owner_id in ids and course.id not in courses_with_classes:
            course_ids[course.owner_id].add(course.id)

    class_id_pool = set().union(*class_ids.values()) if class_ids else set()
    enrollments = (db.session.query(ClassEnrollment.school_class_id, Student.student_code)
                   .join(Student, Student.id == ClassEnrollment.student_id)
                   .filter(ClassEnrollment.school_class_id.in_(class_id_pool),
                           ClassEnrollment.started_on <= today,
                           or_(ClassEnrollment.ended_on.is_(None),
                               ClassEnrollment.ended_on > today)).distinct().all()
                   if class_id_pool else [])
    class_roster = defaultdict(set)
    for class_id, code in enrollments:
        class_roster[class_id].add(code)

    all_course_ids = set().union(*course_ids.values()) if course_ids else set()
    # Học liệu thực tế được liên kết với học phần, kể cả video trong playlist.
    video_requirements = defaultdict(set)
    if all_course_ids:
        for c_id, v_id in (db.session.query(CourseVideo.course_id, CourseVideo.video_id)
                          .filter(CourseVideo.course_id.in_(all_course_ids)).all()):
            video_requirements[c_id].add(v_id)
        for c_id, v_id in (db.session.query(CoursePlaylist.course_id, PlaylistVideo.video_id)
                          .join(PlaylistVideo, PlaylistVideo.playlist_id == CoursePlaylist.playlist_id)
                          .filter(CoursePlaylist.course_id.in_(all_course_ids),
                                  CoursePlaylist.active.is_(True)).distinct().all()):
            video_requirements[c_id].add(v_id)

    # Căn cứ sinh viên đang thuộc đúng lớp và học phần trong phân công hiện hành.
    roster = {}
    student_scopes = {}
    for lecturer_id in ids:
        roster[lecturer_id] = set().union(*(class_roster[cid] for cid in class_ids[lecturer_id])) if class_ids[lecturer_id] else set()
        student_scopes[lecturer_id] = defaultdict(set)
        for cid, class_id in scope[lecturer_id]:
            for code in class_roster[class_id]:
                student_scopes[lecturer_id][code].add((cid, class_id))

    # QR đã tạo tính theo người tạo mã, kể cả mã hiện đã ngừng hoạt động;
    # không nhập nhằng với giảng viên nhận bàn giao môn.
    qr_counts = defaultdict(int)
    # Mỗi QR video lẻ = 1 video; mỗi QR playlist = số video trong playlist.
    # Cộng theo TỪNG mã QR: cùng video có trong hai playlist vẫn tính hai lần,
    # vì đây là số video học liệu được bao phủ bởi các mã QR đã tạo.
    # Sử dụng thành viên playlist đang đồng bộ tại thời điểm lập báo cáo.
    playlist_sizes = {
        playlist_id: count for playlist_id, count in
        db.session.query(PlaylistVideo.playlist_id, db.func.count(db.distinct(PlaylistVideo.video_id)))
        .group_by(PlaylistVideo.playlist_id).all()
    }
    video_counts = defaultdict(int)
    owned_qrs = (db.session.query(QrCode.owner_id, QrCode.target_type, QrCode.playlist_id)
                 .filter(QrCode.owner_id.in_(ids)).all())
    for owner_id, target_type, playlist_id in owned_qrs:
        qr_counts[owner_id] += 1
        if (target_type or "video") == "playlist" or playlist_id is not None:
            video_counts[owner_id] += playlist_sizes.get(playlist_id, 0)
        else:
            video_counts[owner_id] += 1

    relevant_courses = {c for items in scope.values() for c, _ in items}
    # Quét QR phải gắn được với hoạt động của chính GV: QR do họ tạo
    # hoặc QR thuộc môn/lớp họ đang trực tiếp giảng dạy.
    # Dùng ScanLog.id gốc và tập mã SV để một SV quét nhiều lần vẫn tính một em.
    scans = (db.session.query(ScanLog.participant_code, ScanLog.class_code,
                              ScanLog.course_id, QrCode.course_id, QrCode.owner_id,
                              ScanLog.success)
             .join(QrCode, QrCode.id == ScanLog.qr_id)
             .filter(ScanLog.role == "SV",
                     or_(QrCode.owner_id.in_(ids),
                         ScanLog.course_id.in_(relevant_courses),
                         QrCode.course_id.in_(relevant_courses))).all()
             if ids else [])

    scanned = defaultdict(set)
    successful = defaultdict(set)
    # Ánh xạ lớp để tránh N+1 truy vấn và không lẫn mã lớp với ID.
    codes_by_class = {cl.id: cl.code for _, cl in links}
    course_class_codes = {
        uid: {(cid, codes_by_class.get(class_id)) for cid, class_id in pairs}
        for uid, pairs in scope.items()
    }
    # Với nhật ký cũ thiếu mã lớp, chỉ quy thuộc khi sinh viên thuộc
    # DUY NHẤT một lớp phù hợp của chính môn đó; không suy đoán mơ hồ.
    student_course_classes = defaultdict(lambda: defaultdict(set))
    for uid, students in student_scopes.items():
        for code, assigned_scopes in students.items():
            for cid, class_id in assigned_scopes:
                student_course_classes[uid][(code, cid)].add(codes_by_class.get(class_id))
    class_codes_by_user = {
        uid: {codes_by_class.get(class_id) for class_id in class_ids[uid]}
        for uid in ids
    }
    for code, class_code, scanned_course, qr_course, qr_owner, success in scans:
        cid = scanned_course or qr_course
        for uid in ids:
            if code not in roster[uid]:
                continue
            inferred_class_code = class_code
            if not inferred_class_code and cid is not None:
                possible = student_course_classes[uid].get((code, cid), set())
                inferred_class_code = next(iter(possible)) if len(possible) == 1 else None
            matches_course_class = (cid, inferred_class_code) in course_class_codes.get(uid, set())
            matches_own_qr = (qr_owner == uid and inferred_class_code in class_codes_by_user[uid])
            if matches_course_class or matches_own_qr:
                scanned[uid].add(code)
                if success:
                    successful[uid].add(code)

    # Cùng quy tắc với bảng B: thành tích xem của SV theo video,
    # không mất kết quả khi cùng video được học từ QR/học phần khác.
    # Mỗi phiên đủ ngưỡng hiện hành mới được công nhận, không tin cờ completed cũ.
    relevant_videos = set().union(*video_requirements.values()) if video_requirements else set()
    completed_video_pairs = set()
    if relevant_videos:
        completed_video_pairs = set(
            db.session.query(WatchSession.participant_code, WatchSession.video_id)
            .filter(WatchSession.role == "SV",
                    WatchSession.video_id.in_(relevant_videos),
                    WatchSession.duration_seconds > 0,
                    WatchSession.estimated_watch_seconds > 0,
                    WatchSession.estimated_watch_seconds >= WatchSession.duration_seconds * threshold)
            .distinct().all()
        )

    results = []
    for person in people:
        uid = person.id
        finished = 0
        for code, assigned_scopes in student_scopes[uid].items():
            # Chỉ cần một học phần chưa xem đủ video là chưa hoàn thành toàn bộ.
            if not assigned_scopes:
                continue
            if all(video_requirements.get(cid) and all(
                (code, vid) in completed_video_pairs
                for vid in video_requirements[cid]
            ) for cid, class_id in assigned_scopes):
                finished += 1
        results.append({
            "lecturer": person.name or person.email,
            "email": person.email,
            "courses": len(course_ids[uid]),
            "qr": qr_counts[uid],
            "videos": video_counts[uid],
            "classes": len(class_ids[uid]),
            "roster": len(roster[uid]),
            "scanned": len(scanned[uid]),
            "successful": len(successful[uid]),
            "finished": finished,
        })
    return results
