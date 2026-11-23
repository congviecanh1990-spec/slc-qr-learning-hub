"""Thực nghiệm QR ghép cặp: cùng giảng viên, học phần, đầu ra và khối lượng.

Đo thủ công và Web App theo thời gian TƯƠNG TÁC trọn quy trình bằng đồng hồ.
Nhật ký ExperimentRun cũ chỉ đo backend không được dùng để suy tỷ lệ tiết kiệm.
Không trộn video riêng với playlist, không dùng số video playlist làm số QR.
"""
import math
import re


RESEARCH_PAIR_KINDS = (
    ("QR_VIDEO_RIENG", "QR video lẻ (tạo từng mã)"),
    ("QR_VIDEO_HANG_LOAT", "QR video hàng loạt"),
    ("QR_PLAYLIST", "QR playlist (mỗi playlist một QR)"),
)
RESEARCH_PAIR_KIND_NAMES = dict(RESEARCH_PAIR_KINDS)


def _positive_int(value, label, allow_zero=False):
    raw = str(value if value is not None else "").strip()
    if not raw.isascii() or not raw.isdigit():
        raise ValueError(f"{label} phải là số nguyên không âm.")
    number = int(raw)
    if number < (0 if allow_zero else 1) or number > 100000:
        raise ValueError(f"{label} phải nằm trong khoảng hợp lệ.")
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
    """Trả lại kiểu dữ liệu an toàn, không quyết định quyền với lecturer/course."""
    pair_code = (form.get("pair_code") or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9_-]{3,64}", pair_code):
        raise ValueError("Mã lượt đo phải dài 3–64 ký tự: chữ không dấu, số, gạch ngang hoặc gạch dưới.")
    kind = (form.get("task_kind") or "").strip()
    if kind not in RESEARCH_PAIR_KIND_NAMES:
        raise ValueError("Phải chọn đúng loại nhiệm vụ tạo mã QR.")
    lecturer_id = _positive_int(form.get("lecturer_id"), "Giảng viên")
    course_id = _positive_int(form.get("course_id"), "Học phần/mô đun")
    video_count = _positive_int(form.get("video_count", "0"), "Số video lẻ", True)
    playlist_count = _positive_int(form.get("playlist_count", "0"), "Số playlist", True)
    playlist_video_count = _positive_int(form.get("playlist_video_count", "0"), "Video trong playlist", True)
    qr_count = _positive_int(form.get("qr_count"), "Số mã QR hoàn thành")
    manual_operations = _positive_int(form.get("manual_operations"), "Số thao tác thủ công")
    manual_seconds = _positive_seconds(form.get("manual_seconds"), "Thời gian thủ công")

    if kind == "QR_PLAYLIST":
        if video_count or not playlist_count or playlist_video_count < playlist_count or qr_count != playlist_count:
            raise ValueError("Đo QR playlist: video lẻ = 0; số QR bằng số playlist, tổng video playlist phải ít nhất bằng số playlist.")
    else:
        if not video_count or playlist_count or playlist_video_count or qr_count != video_count:
            raise ValueError("Đo QR video: số QR bằng số video lẻ; số playlist và video trong playlist = 0.")

    raw_ops = (form.get("webapp_operations") or "").strip()
    raw_seconds = (form.get("webapp_seconds") or "").strip()
    if bool(raw_ops) != bool(raw_seconds):
        raise ValueError("Phải nhập cả số thao tác và thời gian Web App, hoặc để trống cả hai để bổ sung sau.")
    webapp_operations = _positive_int(raw_ops, "Số thao tác Web App") if raw_ops else None
    webapp_seconds = _positive_seconds(raw_seconds, "Thời gian Web App") if raw_seconds else None
    note = (form.get("note") or "").strip()[:2000]
    return dict(
        pair_code=pair_code, lecturer_id=lecturer_id, course_id=course_id, task_kind=kind,
        video_count=video_count, playlist_count=playlist_count,
        playlist_video_count=playlist_video_count, qr_count=qr_count,
        manual_operations=manual_operations, manual_seconds=manual_seconds,
        webapp_operations=webapp_operations, webapp_seconds=webapp_seconds, note=note,
    )


def pair_metrics(pairs):
    """Tính trên các cặp tương đồng và đủ hai phép đo, bỏ qua bản ghi cũ."""
    valid = [p for p in pairs if p.active and p.webapp_operations is not None
             and p.webapp_seconds is not None and p.manual_seconds > 0 and p.qr_count > 0]
    result = []
    for key, label in RESEARCH_PAIR_KINDS:
        rows = [p for p in valid if p.task_kind == key]
        if not rows:
            continue
        qrs = sum(p.qr_count for p in rows)
        manual_time = sum(p.manual_seconds for p in rows)
        app_time = sum(p.webapp_seconds for p in rows)
        manual_ops = sum(p.manual_operations for p in rows)
        app_ops = sum(p.webapp_operations for p in rows)
        result.append(dict(
            key=key, label=label, n=len(rows), qr_count=qrs,
            manual_time=round(manual_time, 2), app_time=round(app_time, 2),
            manual_per_qr=round(manual_time/qrs, 2), app_per_qr=round(app_time/qrs, 2),
            manual_ops=manual_ops, app_ops=app_ops,
            manual_ops_per_qr=round(manual_ops/qrs, 2),
            app_ops_per_qr=round(app_ops/qrs, 2),
            time_reduction=round(100*(manual_time-app_time)/manual_time, 1),
            ops_reduction=round(100*(manual_ops-app_ops)/manual_ops, 1),
        ))
    if valid:
        mt=sum(p.manual_seconds for p in valid)
        at=sum(p.webapp_seconds for p in valid)
        mo=sum(p.manual_operations for p in valid)
        ao=sum(p.webapp_operations for p in valid)
        totals=dict(paired_count=len(valid), qr_count=sum(p.qr_count for p in valid),
                    time_reduction=round(100*(mt-at)/mt, 1) if mt>0 else None,
                    ops_reduction=round(100*(mo-ao)/mo, 1) if mo>0 else None)
    else:
        totals=dict(paired_count=0, qr_count=0, time_reduction=None, ops_reduction=None)
    return result, totals
