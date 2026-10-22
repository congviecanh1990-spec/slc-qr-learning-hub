from __future__ import annotations

from datetime import datetime, timezone
import requests
from flask import current_app

from models import db, OAuthAccount, ConnectedGoogleAccount, YouTubeChannel, Playlist, Video, PlaylistVideo, Course, CourseVideo, CoursePlaylist, ErrorLog, utcnow
from security import decrypt_json, encrypt_json

YOUTUBE_API = "https://www.googleapis.com/youtube/v3"
TOKEN_URL = "https://oauth2.googleapis.com/token"


class YouTubeSyncError(RuntimeError):
    """Thông báo an toàn cho người dùng; lý do API gốc được ghi tại nhật ký lỗi."""
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


class SyncIssues(list):
    """Giữ tương thích với các nơi đang nối chuỗi lỗi, kèm mã phân loại."""
    def __init__(self):
        super().__init__()
        self.codes = []


def _api_error_code(response):
    """Đọc mã lỗi YouTube nếu có; không đưa URL/token/JSON kỹ thuật lên giao diện."""
    try:
        details = (response.json() or {}).get("error") or {}
        reasons = [e.get("reason", "") for e in details.get("errors", []) if isinstance(e, dict)]
        for item in details.get("details", []):
            if isinstance(item, dict):
                reasons.append(item.get("reason", ""))
        reasons = {str(r).lower() for r in reasons}
    except (ValueError, TypeError, AttributeError):
        reasons = set()
    if reasons & {"quotaexceeded", "dailylimitexceeded", "userratelimitexceeded", "ratelimitexceeded", "resourceexhausted"}:
        return "quota"
    if reasons & {"accessnotconfigured", "servicedisabled", "apidisabled"}:
        return "configuration"
    if reasons & {"insufficientpermissions", "forbidden", "autherror", "youtubesignuprequired", "accountdelegationforbidden"}:
        return "permission"
    return None


def _friendly_http_error(response):
    status = response.status_code
    code = _api_error_code(response)
    if code == "quota" or status == 429:
        return YouTubeSyncError("quota", "YouTube đang giới hạn số lượt truy cập. Hãy thử đồng bộ lại sau.")
    if code == "configuration":
        return YouTubeSyncError("configuration", "Dịch vụ YouTube Data API chưa sẵn sàng trên ứng dụng. Vui lòng liên hệ quản trị viên.")
    if status in (401, 403):
        return YouTubeSyncError("permission", "YouTube chưa cho phép truy cập dữ liệu kênh của tài khoản này (lỗi quyền truy cập). Hãy kiểm tra tài khoản Google đã chọn và cấp lại quyền khi kết nối.")
    if status == 404:
        return YouTubeSyncError("not_found", "Một kênh hoặc danh sách phát không còn truy cập được trên YouTube. Hãy kiểm tra lại nội dung kênh.")
    if status >= 500:
        return YouTubeSyncError("temporary", "YouTube đang gặp sự cố kết nối. Hãy thử đồng bộ lại sau.")
    return YouTubeSyncError("error", "YouTube chưa trả về được dữ liệu kênh. Hãy thử đồng bộ lại sau.")


def _friendly_sync_error(exc):
    if isinstance(exc, YouTubeSyncError):
        return exc
    if isinstance(exc, requests.exceptions.Timeout):
        return YouTubeSyncError("temporary", "Kết nối tới YouTube bị quá thời gian. Hãy thử lại sau.")
    if isinstance(exc, requests.exceptions.RequestException):
        return YouTubeSyncError("temporary", "Không kết nối được tới YouTube. Hãy kiểm tra đường truyền và thử lại.")
    # Các lỗi nội bộ bất ngờ không được hiển thị trực tiếp dưới dạng traceback/URL.
    if isinstance(exc, RuntimeError) and str(exc) in (
        "Không tìm thấy kênh YouTube thuộc tài khoản này.",
        "Kênh YouTube này đã được kết nối với hồ sơ giảng viên khác.",
    ):
        return YouTubeSyncError("no_channel" if "Không tìm thấy" in str(exc) else "conflict", str(exc))
    return YouTubeSyncError("error", "Chưa thể hoàn tất đồng bộ YouTube. Hãy thử lại hoặc liên hệ quản trị viên.")


def build_sync_summary(channels, issues):
    """Kết quả có thể hiển thị công khai; không suy đoán kênh trống từ lỗi API."""
    channel_count = len(channels)
    video_count = sum(sum(1 for video in channel.videos if video.is_available) for channel in channels)
    if issues:
        causes = "; ".join(issues)
        if channel_count:
            return {"ok": False, "status": "partial", "channel_count": channel_count,
                    "video_count": video_count,
                    "message": f"Đã cập nhật được {channel_count} kênh, nhưng một số tài khoản chưa đồng bộ được: {causes} Dữ liệu đã có vẫn được giữ nguyên."}
        codes = getattr(issues, "codes", [])
        priority = ("configuration", "quota", "permission", "conflict", "no_channel", "temporary", "error")
        status = next((code for code in priority if code in codes), "error")
        return {"ok": False, "status": status, "channel_count": 0, "video_count": 0,
                "message": "Chưa đồng bộ được kênh YouTube. " + causes + " Bạn vẫn có thể vào hệ thống và kiểm tra kết nối tại mục Kênh YouTube."}
    if not channel_count:
        return {"ok": False, "status": "no_channel", "channel_count": 0, "video_count": 0,
                "message": "Chưa tìm thấy kênh YouTube được kết nối. Vui lòng kiểm tra tài khoản Google và kết nối kênh YouTube."}
    if not video_count:
        return {"ok": True, "status": "empty", "channel_count": channel_count, "video_count": 0,
                "message": f"Đã kết nối và kiểm tra {channel_count} kênh YouTube, nhưng chưa tìm thấy video học liệu có thể đồng bộ. Bạn có thể vào hệ thống bình thường. Nếu kênh chưa đăng video, hãy đăng video lên YouTube rồi chọn 'Đồng bộ lại' trong mục Kênh YouTube."}
    return {"ok": True, "status": "synced", "channel_count": channel_count, "video_count": video_count,
            "message": f"Đã đồng bộ {channel_count} kênh YouTube và {video_count} video học liệu."}


def _log_error(module, message, details=None):
    db.session.add(ErrorLog(module=module, message=message[:500], details=(details or "")[:10000]))
    db.session.commit()


def _token_for_user(user, credential=None):
    account = credential or OAuthAccount.query.filter_by(user_id=user.id).first()
    if not account:
        raise RuntimeError("Tài khoản chưa có token Google/YouTube.")
    token = decrypt_json(account.token_encrypted)
    expires_at = token.get("expires_at")
    if expires_at and float(expires_at) <= datetime.now(timezone.utc).timestamp() + 60:
        refresh = token.get("refresh_token")
        if not refresh:
            raise RuntimeError("Token đã hết hạn và không có refresh_token. Hãy đăng nhập Google lại.")
        resp = requests.post(
            TOKEN_URL,
            data={
                "client_id": current_app.config["GOOGLE_CLIENT_ID"],
                "client_secret": current_app.config["GOOGLE_CLIENT_SECRET"],
                "refresh_token": refresh,
                "grant_type": "refresh_token",
            },
            timeout=20,
        )
        resp.raise_for_status()
        new_data = resp.json()
        token["access_token"] = new_data["access_token"]
        token["expires_in"] = new_data.get("expires_in", 3600)
        token["expires_at"] = datetime.now(timezone.utc).timestamp() + token["expires_in"]
        if new_data.get("scope"):
            token["scope"] = new_data["scope"]
        account.token_encrypted = encrypt_json(token)
        db.session.commit()
    return token["access_token"]


def _get(user, path, params, credential=None):
    access = _token_for_user(user, credential)
    headers = {"Authorization": f"Bearer {access}"}
    resp = requests.get(f"{YOUTUBE_API}/{path}", params=params, headers=headers, timeout=30)
    if resp.status_code == 401:
        account = credential or OAuthAccount.query.filter_by(user_id=user.id).first()
        token = decrypt_json(account.token_encrypted)
        token["expires_at"] = 0
        account.token_encrypted = encrypt_json(token)
        db.session.commit()
        access = _token_for_user(user, credential)
        headers = {"Authorization": f"Bearer {access}"}
        resp = requests.get(f"{YOUTUBE_API}/{path}", params=params, headers=headers, timeout=30)
    if not resp.ok:
        _log_error("youtube_api", f"GET {path} lỗi {resp.status_code}", resp.text)
        raise _friendly_http_error(resp)
    return resp.json()


def _parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _thumb(snippet):
    thumbs = (snippet or {}).get("thumbnails") or {}
    for k in ("maxres", "standard", "high", "medium", "default"):
        if k in thumbs:
            return thumbs[k].get("url")
    return None


def sync_my_channel(user, credential=None):
    data = _get(user, "channels", {"part": "snippet,contentDetails", "mine": "true", "maxResults": 50}, credential)
    items = data.get("items", [])
    if not items:
        raise RuntimeError("Không tìm thấy kênh YouTube thuộc tài khoản này.")

    synced = []
    for item in items:
        cid = item["id"]
        snippet = item.get("snippet", {})
        uploads = item.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
        existing_other = YouTubeChannel.query.filter_by(channel_id=cid).first()
        if existing_other and existing_other.user_id != user.id:
            raise RuntimeError("Kênh YouTube này đã được kết nối với hồ sơ giảng viên khác.")
        channel = YouTubeChannel.query.filter_by(user_id=user.id, channel_id=cid).first()
        if not channel:
            channel = YouTubeChannel(user_id=user.id, channel_id=cid)
            db.session.add(channel)
        channel.connected_account_id = credential.id if isinstance(credential, ConnectedGoogleAccount) else None
        channel.title = snippet.get("title", cid)
        channel.uploads_playlist_id = uploads
        channel.thumbnail_url = _thumb(snippet)
        channel.last_synced_at = utcnow()
        db.session.flush()
        playlists = sync_playlists(user, channel, credential)
        # Đồng bộ nội dung của từng playlist do giảng viên tạo để Web App có thể
        # gán playlist vào học phần và tạo QR playlist động.
        for playlist in playlists:
            sync_playlist_items(user, channel, playlist.youtube_playlist_id, credential=credential)
        if uploads:
            sync_playlist_items(user, channel, uploads, uploads_playlist=True, credential=credential)
        # Kiểm tra lại CẢ các video từng lưu nhưng không còn nằm trong playlist hiện tại;
        # nhờ đó phát hiện video đã xóa/đổi quyền ngay khi GV bấm Đồng bộ lại.
        stored_ids = [v.youtube_video_id for v in Video.query.filter_by(channel_id=channel.id).all()]
        for i in range(0, len(stored_ids), 50):
            sync_video_ids(user, channel, stored_ids[i:i+50], credential)
        synced.append(channel)
    # Sau khi đồng bộ YouTube, mọi playlist đã gán cho học phần được xem như
    # nguồn dữ liệu động: video mới tự vào học phần, video đã gỡ khỏi playlist
    # tự rời học phần nếu không được gán riêng hoặc không còn ở playlist khác.
    _reconcile_course_playlist_assignments(user)
    db.session.commit()
    return synced


def _reconcile_course_playlist_assignments(user):
    courses = Course.query.filter_by(owner_id=user.id, active=True).all()
    for course in courses:
        active_links = CoursePlaylist.query.filter_by(course_id=course.id, active=True).all()
        playlist_ids = [x.playlist_id for x in active_links if x.playlist_id]
        desired = {}
        if playlist_ids:
            for video_id, playlist_id in (db.session.query(PlaylistVideo.video_id, PlaylistVideo.playlist_id)
                                          .filter(PlaylistVideo.playlist_id.in_(playlist_ids)).all()):
                desired.setdefault(video_id, playlist_id)

        existing = {x.video_id: x for x in CourseVideo.query.filter_by(course_id=course.id).all()}
        for video_id, playlist_id in desired.items():
            link = existing.get(video_id)
            if link:
                if not link.manual_added:
                    link.source_playlist_id = playlist_id
                continue
            db.session.add(CourseVideo(
                course_id=course.id, video_id=video_id, added_by=user.id,
                source_playlist_id=playlist_id, manual_added=False,
            ))

        for video_id, link in list(existing.items()):
            if video_id not in desired and not bool(getattr(link, "manual_added", True)):
                db.session.delete(link)
        db.session.flush()


def sync_playlists(user, channel, credential=None):
    seen_ids = set()
    synced_playlists = []
    page = None
    while True:
        params = {"part": "snippet,status", "channelId": channel.channel_id, "maxResults": 50}
        if page:
            params["pageToken"] = page
        data = _get(user, "playlists", params, credential)
        for item in data.get("items", []):
            pid = item["id"]
            seen_ids.add(pid)
            snippet = item.get("snippet", {})
            p = Playlist.query.filter_by(youtube_playlist_id=pid).first()
            if not p:
                p = Playlist(channel_id=channel.id, youtube_playlist_id=pid)
                db.session.add(p)
            p.channel_id = channel.id
            p.title = snippet.get("title", pid)
            p.description = snippet.get("description")
            p.privacy_status = item.get("status", {}).get("privacyStatus")
            p.is_available = True
            p.last_synced_at = utcnow()
            synced_playlists.append(p)
        db.session.flush()
        page = data.get("nextPageToken")
        if not page:
            break

    # Playlist do người dùng tạo nhưng không còn được API trả về được đánh dấu
    # không khả dụng; QR đã phát hành vẫn được giữ để thông báo/khắc phục.
    for p in Playlist.query.filter_by(channel_id=channel.id).all():
        if p.youtube_playlist_id == channel.uploads_playlist_id:
            continue
        if p.youtube_playlist_id not in seen_ids:
            p.is_available = False
            p.last_synced_at = utcnow()
    db.session.flush()
    return synced_playlists


def sync_playlist_items(user, channel, playlist_youtube_id, uploads_playlist=False, credential=None):
    """Đồng bộ playlist nhưng không coi video của kênh khác là video của GV.

    Một playlist có thể chứa bất kỳ video công khai nào trên YouTube. Chỉ đưa
    video do kênh đã được giảng viên kết nối thật sự đăng tải vào kho học liệu.
    Những liên kết sai từ lần đồng bộ cũ bị bỏ; bản ghi Video/QR vẫn được giữ.
    """
    video_ids = []
    item_meta = {}
    page = None
    while True:
        params = {
            "part": "snippet,contentDetails",
            "playlistId": playlist_youtube_id,
            "maxResults": 50,
        }
        if page:
            params["pageToken"] = page
        data = _get(user, "playlistItems", params, credential)
        for item in data.get("items", []):
            vid = item.get("contentDetails", {}).get("videoId") or item.get("snippet", {}).get("resourceId", {}).get("videoId")
            if vid:
                video_ids.append(vid)
                item_meta[vid] = item
        page = data.get("nextPageToken")
        if not page:
            break

    for i in range(0, len(video_ids), 50):
        sync_video_ids(user, channel, video_ids[i:i + 50], credential)

    playlist = Playlist.query.filter_by(youtube_playlist_id=playlist_youtube_id).first()
    if not playlist and uploads_playlist:
        playlist = Playlist(
            channel_id=channel.id,
            youtube_playlist_id=playlist_youtube_id,
            title="Uploads",
            description="Danh sách video tải lên của kênh",
            privacy_status="public",
            is_available=True,
            last_synced_at=utcnow(),
        )
        db.session.add(playlist)
        db.session.flush()

    if playlist:
        playlist.is_available = True
        playlist.last_synced_at = utcnow()
        current_video_ids = set()
        for vid in video_ids:
            video = Video.query.filter_by(youtube_video_id=vid).first()
            # Không phải video thuộc một kênh GV đã kết nối thì không nhận.
            if not video or video.channel.user_id != user.id or not video.uploader_channel_id:
                continue
            if video.uploader_channel_id != video.channel.channel_id:
                continue
            current_video_ids.add(video.id)
            link = PlaylistVideo.query.filter_by(playlist_id=playlist.id, video_id=video.id).first()
            position = item_meta.get(vid, {}).get("snippet", {}).get("position")
            if not link:
                db.session.add(PlaylistVideo(playlist_id=playlist.id, video_id=video.id, position=position))
            else:
                link.position = position
        # Gỡ các quan hệ playlist -> video đã bị xóa khỏi playlist hoặc được
        # xác minh là thuộc kênh không kết nối. Không xóa video hoặc lịch sử QR.
        for link in PlaylistVideo.query.filter_by(playlist_id=playlist.id).all():
            if link.video_id not in current_video_ids:
                db.session.delete(link)
    db.session.commit()


def sync_video_ids(user, channel, video_ids, credential=None):
    """Kiểm tra đúng kênh ĐĂNG TẢI qua snippet.channelId của videos.list.

    Khác với video.channel_id trong DB, kết quả của YouTube API mới là căn cứ
    quyền sở hữu; video nằm trong playlist của GV chưa chắc do GV tải lên.
    """
    if credential is None and channel.connected_account_id:
        credential = db.session.get(ConnectedGoogleAccount, channel.connected_account_id)
    if not video_ids:
        return
    data = _get(
        user,
        "videos",
        {
            "part": "snippet,status,contentDetails",
            "id": ",".join(video_ids),
            "maxResults": 50,
        },
        credential,
    )
    returned = set()
    for item in data.get("items", []):
        vid = item["id"]
        returned.add(vid)
        snippet = item.get("snippet", {})
        status = item.get("status", {})
        content = item.get("contentDetails", {})
        actual_youtube_channel_id = snippet.get("channelId")

        video = Video.query.filter_by(youtube_video_id=vid).first()
        if video and video.channel.user_id != user.id:
            # Tuyệt đối không sửa video đã được kết nối với GV khác.
            continue

        owning_channel = (YouTubeChannel.query.filter_by(
            user_id=user.id, channel_id=actual_youtube_channel_id).first()
            if actual_youtube_channel_id else None)
        if not video and not owning_channel:
            # Video của kênh khác trong playlist: không thêm vào Kho video.
            continue
        if not video:
            video = Video(channel_id=owning_channel.id, youtube_video_id=vid)
            db.session.add(video)
        if owning_channel:
            # Sửa liên kết sai từ các phiên bản cũ, khi một video của kênh B bị
            # đưa nhầm vào kênh A vì xuất hiện trong playlist A.
            video.channel_id = owning_channel.id
            video.channel = owning_channel
        video.uploader_channel_id = actual_youtube_channel_id
        video.title = snippet.get("title", vid)
        video.description = snippet.get("description")
        video.published_at = _parse_dt(snippet.get("publishedAt"))
        video.privacy_status = status.get("privacyStatus")
        video.upload_status = status.get("uploadStatus")
        video.embeddable = status.get("embeddable")
        video.is_available = True
        video.duration_iso = content.get("duration")
        video.thumbnail_url = _thumb(snippet)
        video.last_synced_at = utcnow()

    missing = set(video_ids) - returned
    for vid in missing:
        video = Video.query.filter_by(youtube_video_id=vid).first()
        if video and video.channel.user_id == user.id:
            video.is_available = False
            video.last_synced_at = utcnow()
    db.session.commit()


def sync_all_connected_channels(user):
    """Đồng bộ kênh chính và các tài khoản Google bổ sung; trả về các lỗi riêng lẻ."""
    channels, errors = [], SyncIssues()
    credentials = [None] + ConnectedGoogleAccount.query.filter_by(user_id=user.id).all()
    for credential in credentials:
        try:
            channels.extend(sync_my_channel(user, credential))
        except Exception as exc:
            db.session.rollback()
            label = credential.email if credential is not None else user.email
            friendly = _friendly_sync_error(exc)
            errors.codes.append(friendly.code)
            errors.append(f"{label}: {friendly}")
    return channels, errors


def reconcile_user(user):
    channels, errors = sync_all_connected_channels(user)
    if errors:
        raise RuntimeError("; ".join(errors))
    return sum(len(channel.videos) for channel in channels)
