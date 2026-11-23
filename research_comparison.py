"""Kiểm tra và tổng hợp đối chứng QR theo từng lượt giảng viên.

Dữ liệu thủ công do quản trị viên nhập; Web App tự lấy mốc thời gian từ server,
đếm thao tác giao diện và xác minh QR mới. Không dùng thời gian xử lý backend
hoặc các số liệu Web App nhập thủ công từ phiên bản cũ để kết luận hiệu quả.
"""
import math


RESEARCH_PAIR_KINDS = (
    ("QR_TUNG_VIDEO_PLAYLIST", "Tạo mã QR cho từng video hoặc từng playlist"),
    ("QR_VIDEO_HANG_LOAT", "Tạo mã QR hàng loạt cho video"),
)
RESEARCH_PAIR_KIND_NAMES = dict(RESEARCH_PAIR_KINDS)
LEGACY_KIND_MAPPING = {
    "QR_VIDEO_RIENG": "QR_TUNG_VIDEO_PLAYLIST",
    "QR_PLAYLIST": "QR_TUNG_VIDEO_PLAYLIST",
}


def normalize_kind(kind):
    return LEGACY_KIND_MAPPING.get(kind, kind)


def _positive_int(value, label, allow_zero=False):
    raw = str(value if value is not None else "").strip()
    if not raw.isascii() or not raw.isdigit():
        raise ValueError(f"{label} phải là số nguyên hợp lệ.")
    number = int(raw)
    if not (0 if allow_zero else 1) <= number <= 100000:
        raise ValueError(f"{label} nằm ngoài giới hạn hợp lệ.")
    return number


def _positive_seconds(value, label):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} phải là số giây hợp lệ.") from None
    if not math.isfinite(number) or not (0 < number <= 864000):
        raise ValueError(f"{label} phải lớn hơn 0 và không quá 10 ngày.")
    return number


def validate_pair_form(form):
    """Chỉ nhận dữ liệu đối chứng THỦ CÔNG, không nhận số đo Web App từ biểu mẫu."""
    kind = (form.get("task_kind") or "").strip()
    if kind not in RESEARCH_PAIR_KIND_NAMES:
        raise ValueError("Chọn một trong hai loại nhiệm vụ tạo mã QR.")
    lecturer_id = _positive_int(form.get("lecturer_id"), "Giảng viên")
    course_id = _positive_int(form.get("course_id"), "Học phần/mô đun")
    video_count = _positive_int(form.get("video_count", "0"), "Số video lẻ", True)
    playlist_count = _positive_int(form.get("playlist_count", "0"), "Số playlist", True)
    playlist_video_count = _positive_int(form.get("playlist_video_count", "0"), "Video trong playlist", True)
    manual_operations = _positive_int(form.get("manual_operations"), "Số thao tác thủ công")
    manual_seconds = _positive_seconds(form.get("manual_seconds"), "Thời gian thủ công")

    if kind == "QR_VIDEO_HANG_LOAT":
        if not video_count or playlist_count or playlist_video_count:
            raise ValueError("QR video hàng loạt chỉ gồm video lẻ; không được có playlist.")
    elif video_count + playlist_count < 1:
        raise ValueError("Phải có video hoặc playlist để tạo mã QR.")
    if playlist_count == 0 and playlist_video_count != 0:
        raise ValueError("Không có playlist thì số video trong playlist phải bằng 0.")
    if playlist_count > 0 and playlist_video_count < playlist_count:
        raise ValueError("Tổng video trong các playlist phải ít nhất bằng số playlist.")

    qr_count = video_count + playlist_count
    # Một QR playlist bao phủ nhiều video, nhưng bản thân chỉ là một mã QR.
    # Định mức thời gian / video dùng số video lẻ + số video trong playlist.
    video_coverage = video_count + playlist_video_count
    if video_coverage <= 0:
        raise ValueError("Số video học liệu phải lớn hơn 0.")

    note = (form.get("note") or "").strip()[:2000]
    return dict(
        lecturer_id=lecturer_id, course_id=course_id, task_kind=kind,
        video_count=video_count, playlist_count=playlist_count,
        playlist_video_count=playlist_video_count, qr_count=qr_count,
        manual_operations=manual_operations, manual_seconds=manual_seconds, note=note,
    )


def video_coverage(pair):
    return max(0, (pair.video_count or 0) + (pair.playlist_video_count or 0))


def pair_metrics(pairs):
    """Chỉ dùng lượt đã xác minh tự động, tách riêng 2 nhóm nhiệm vụ.

    Mức giảm dựa trên tổng thời gian của cùng các cặp đo. Giây/video =
    tổng thời gian / tổng video học liệu bao phủ, không phải số mã QR.
    """
    valid = [
        p for p in pairs if p.active and getattr(p, "measurement_verified", False)
        and p.webapp_operations is not None and p.webapp_seconds is not None
        and p.manual_seconds > 0 and p.manual_operations > 0
        and video_coverage(p) > 0
    ]
    groups = []
    for key, label in RESEARCH_PAIR_KINDS:
        rows = [p for p in valid if normalize_kind(p.task_kind) == key]
        if not rows:
            continue
        covered = sum(video_coverage(p) for p in rows)
        qrs = sum(p.qr_count for p in rows)
        mt, wt = sum(p.manual_seconds for p in rows), sum(p.webapp_seconds for p in rows)
        mo, wo = sum(p.manual_operations for p in rows), sum(p.webapp_operations for p in rows)
        groups.append(dict(
            key=key, label=label, n=len(rows), qr_count=qrs, video_coverage=covered,
            manual_time=round(mt, 2), app_time=round(wt, 2),
            manual_per_video=round(mt/covered, 2), app_per_video=round(wt/covered, 2),
            manual_ops=mo, app_ops=wo,
            manual_ops_per_qr=round(mo/qrs, 2), app_ops_per_qr=round(wo/qrs, 2),
            time_reduction=round(100*(mt-wt)/mt, 1),
            ops_reduction=round(100*(mo-wo)/mo, 1),
        ))
    if valid:
        mt=sum(p.manual_seconds for p in valid)
        at=sum(p.webapp_seconds for p in valid)
        mo=sum(p.manual_operations for p in valid)
        ao=sum(p.webapp_operations for p in valid)
        totals=dict(
            paired_count=len(valid), qr_count=sum(p.qr_count for p in valid),
            video_coverage=sum(video_coverage(p) for p in valid),
            time_reduction=round(100*(mt-at)/mt, 1),
            ops_reduction=round(100*(mo-ao)/mo, 1),
        )
    else:
        totals=dict(paired_count=0, qr_count=0, video_coverage=0,
                    time_reduction=None, ops_reduction=None)
    return groups, totals
