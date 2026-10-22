from __future__ import annotations

from datetime import datetime, timezone
import json
import requests
from flask import current_app

from models import db, OAuthAccount, ConnectedGoogleAccount, YouTubeChannel, Playlist, Video, PlaylistVideo, Course, CourseVideo, CoursePlaylist, ErrorLog, YouTubeSyncJob, utcnow
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


def build_sync_summary(channels, issues, video_count_override=None):
    """Kết quả có thể hiển thị công khai; không suy đoán kênh trống từ lỗi API."""
    channel_count = len(channels)
    video_count = (sum(sum(1 for video in channel.videos if video.is_available) for channel in channels)
                   if video_count_override is None else video_count_override)
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
        return {"ok": False, "status": "empty", "channel_count": channel_count, "video_count": 0,
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
            timeout=9,
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
    resp = requests.get(f"{YOUTUBE_API}/{path}", params=params, headers=headers, timeout=9)
    if resp.status_code == 401:
        account = credential or OAuthAccount.query.filter_by(user_id=user.id).first()
        token = decrypt_json(account.token_encrypted)
        token["expires_at"] = 0
        account.token_encrypted = encrypt_json(token)
        db.session.commit()
        access = _token_for_user(user, credential)
        headers = {"Authorization": f"Bearer {access}"}
        resp = requests.get(f"{YOUTUBE_API}/{path}", params=params, headers=headers, timeout=9)
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


def sync_video_ids(user, channel, video_ids, credential=None, allow_curated=False):
    """Đọc tối đa 50 video; giữ nguyên nguồn đăng tải thực tế của mỗi video.

    Với playlist của giảng viên, có thể thêm video tuyển chọn công khai/không
    công khai (unlisted) nếu YouTube xác nhận cho nhúng. Video private, không
    nhúng được, đã xóa hoặc không truy cập được không được liên kết mới.
    Mỗi video YouTube có đúng một hàng toàn cục, các playlist GV khác sử dụng
    qua PlaylistVideo chứ không chuyển quyền chủ quản hàng video.
    """
    if credential is None and channel.connected_account_id:
        credential = db.session.get(ConnectedGoogleAccount, channel.connected_account_id)
    video_ids = list(dict.fromkeys(video_ids))
    if not video_ids:
        return 0
    if len(video_ids) > 50:
        raise ValueError("Chỉ kiểm tra tối đa 50 video mỗi lần gọi YouTube API.")
    data = _get(user, "videos", {
        "part": "snippet,status,contentDetails", "id": ",".join(video_ids), "maxResults": 50,
    }, credential)
    returned = set()
    usable = 0
    for item in data.get("items", []):
        vid = item["id"]
        returned.add(vid)
        snippet = item.get("snippet", {})
        status = item.get("status", {})
        content = item.get("contentDetails", {})
        uploader_id = snippet.get("channelId")
        privacy = status.get("privacyStatus")
        can_embed = status.get("embeddable") is True
        accessible = privacy in ("public", "unlisted") and can_embed
        owning_channel = (YouTubeChannel.query.filter_by(user_id=user.id, channel_id=uploader_id).first()
                          if uploader_id else None)
        video = Video.query.filter_by(youtube_video_id=vid).first()
        # Không nhập video lạ từ một ID tùy ý; chỉ video nằm trong playlist GV
        # hoặc video của kênh GV đã kết nối mới được tạo bản ghi.
        if not video and not owning_channel and not (allow_curated and accessible):
            continue
        if not video:
            video = Video(channel_id=(owning_channel or channel).id, youtube_video_id=vid)
            db.session.add(video)
        elif owning_channel and video.channel.user_id == user.id:
            # Giữ video đúng nguồn khi cùng giảng viên sở hữu nhiều kênh.
            video.channel_id = owning_channel.id
            video.channel = owning_channel
        # Metadata lấy từ YouTube; KHÔNG nhận chủ sở hữu dựa trên playlist.
        video.uploader_channel_id = uploader_id
        video.title = snippet.get("title", vid)
        video.description = snippet.get("description")
        video.published_at = _parse_dt(snippet.get("publishedAt"))
        video.privacy_status = privacy
        video.upload_status = status.get("uploadStatus")
        video.embeddable = status.get("embeddable")
        video.is_available = accessible or (owning_channel is not None and privacy == "private")
        video.duration_iso = content.get("duration")
        video.thumbnail_url = _thumb(snippet)
        video.last_synced_at = utcnow()
        if accessible:
            usable += 1
    missing = set(video_ids) - returned
    for vid in missing:
        video = Video.query.filter_by(youtube_video_id=vid).first()
        if video and video.channel.user_id == user.id:
            video.is_available = False
            video.last_synced_at = utcnow()
    db.session.commit()
    return usable


def sync_playlist_page(user, channel, playlist_youtube_id, credential=None,
                       page_token=None, seen_ids=None, uploads_playlist=False):
    """Một trang tối đa 50 mục, tránh đồng bộ toàn bộ playlist trong một HTTP."""
    seen_ids = set(seen_ids or [])
    params = {"part": "snippet,contentDetails", "playlistId": playlist_youtube_id,
              "maxResults": 50}
    if page_token:
        params["pageToken"] = page_token
    data = _get(user, "playlistItems", params, credential)
    video_ids, positions = [], {}
    for item in data.get("items", []):
        vid = (item.get("contentDetails", {}).get("videoId") or
               item.get("snippet", {}).get("resourceId", {}).get("videoId"))
        if vid and vid not in positions:
            video_ids.append(vid)
            positions[vid] = item.get("snippet", {}).get("position")
    sync_video_ids(user, channel, video_ids, credential, allow_curated=not uploads_playlist)
    playlist = Playlist.query.filter_by(youtube_playlist_id=playlist_youtube_id).first()
    if not playlist and uploads_playlist:
        playlist = Playlist(channel_id=channel.id, youtube_playlist_id=playlist_youtube_id,
                            title="Uploads", description="Danh sách video tải lên của kênh",
                            privacy_status="public", is_available=True)
        db.session.add(playlist)
        db.session.flush()
    if not playlist or playlist.channel_id != channel.id:
        raise YouTubeSyncError("permission", "Danh sách phát không thuộc kênh giảng viên đã kết nối.")
    playlist.is_available = True
    playlist.last_synced_at = utcnow()
    for vid in video_ids:
        video = Video.query.filter_by(youtube_video_id=vid).first()
        if not video or not video.is_available or video.embeddable is False or video.privacy_status == "private":
            continue
        # Playlist/uploads phải thuộc đúng kênh kết nối; video tuyển chọn có
        # thể do người khác đăng, nhưng phải được API xác nhận phát được.
        if uploads_playlist and video.uploader_channel_id != channel.channel_id:
            continue
        seen_ids.add(video.id)
        link = PlaylistVideo.query.filter_by(playlist_id=playlist.id, video_id=video.id).first()
        if link:
            link.position = positions.get(vid)
        else:
            db.session.add(PlaylistVideo(playlist_id=playlist.id, video_id=video.id,
                                         position=positions.get(vid)))
    next_page = data.get("nextPageToken")
    if not next_page:
        # Chỉ gỡ mục cũ sau khi đi HẾT tất cả các trang thành công.
        for link in PlaylistVideo.query.filter_by(playlist_id=playlist.id).all():
            if link.video_id not in seen_ids:
                db.session.delete(link)
    db.session.commit()
    return next_page, sorted(seen_ids)


def sync_playlist_items(user, channel, playlist_youtube_id, uploads_playlist=False, credential=None):
    """Đồng bộ đầy đủ khi gọi trực tiếp; luồng UI dùng từng trang riêng."""
    page, seen = None, []
    while True:
        page, seen = sync_playlist_page(user, channel, playlist_youtube_id, credential,
                                       page_token=page, seen_ids=seen,
                                       uploads_playlist=uploads_playlist)
        if not page:
            break


def _sync_channel_catalog(user, credential=None):
    """Nhận diện kênh và danh sách playlist; không tải video ở bước đăng nhập."""
    data = _get(user, "channels", {"part": "snippet,contentDetails", "mine": "true",
                                   "maxResults": 50}, credential)
    items = data.get("items", [])
    if not items:
        raise YouTubeSyncError("no_channel", "Tài khoản Google này chưa có kênh YouTube.")
    tasks = []
    for item in items:
        cid = item["id"]
        existing = YouTubeChannel.query.filter_by(channel_id=cid).first()
        if existing and existing.user_id != user.id:
            raise YouTubeSyncError("conflict", "Kênh này đã được kết nối với hồ sơ giảng viên khác.")
        channel = existing or YouTubeChannel(user_id=user.id, channel_id=cid)
        if not existing:
            db.session.add(channel)
        snippet = item.get("snippet", {})
        uploads = item.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
        channel.connected_account_id = credential.id if credential is not None else None
        channel.title = snippet.get("title", cid)
        channel.uploads_playlist_id = uploads
        channel.thumbnail_url = _thumb(snippet)
        channel.last_synced_at = utcnow()
        db.session.flush()
        playlists = sync_playlists(user, channel, credential)
        for pl in playlists:
            tasks.append({"channel_pk": channel.id, "playlist_pk": pl.id,
                          "credential_pk": credential.id if credential is not None else None,
                          "page_token": None, "seen": []})
        if uploads:
            tasks.append({"channel_pk": channel.id, "uploads": uploads,
                          "credential_pk": credential.id if credential is not None else None,
                          "page_token": None, "seen": []})
    db.session.commit()
    return tasks


def _new_sync_payload(user):
    extras = ConnectedGoogleAccount.query.filter_by(user_id=user.id).all()
    return {"accounts": [None] + [x.id for x in extras], "tasks": [],
            "completed_tasks": 0, "failed": [], "videos_found": 0,
            "seen_video_ids": [],
            "started_at": utcnow().isoformat()}


def start_incremental_sync(user, force=False):
    """Chỉ ghi hàng đợi; không gọi YouTube API nên trả kết quả ngay."""
    job = YouTubeSyncJob.query.filter_by(user_id=user.id).first()
    if job and job.status == "running" and not force:
        return job
    if not job:
        job = YouTubeSyncJob(user_id=user.id)
        db.session.add(job)
    job.status = "running"
    job.finished_at = None
    job.payload_json = json.dumps(_new_sync_payload(user))
    db.session.commit()
    return job


def incremental_sync_state(user):
    job = YouTubeSyncJob.query.filter_by(user_id=user.id).first()
    if not job:
        return {"status": "idle", "message": "Chưa thực hiện đồng bộ YouTube."}
    payload = json.loads(job.payload_json or "{}")
    remaining = len(payload.get("accounts", [])) + len(payload.get("tasks", []))
    return {"status": job.status, "done": int(payload.get("completed_tasks", 0)),
            "remaining": remaining, "videos_found": int(payload.get("videos_found", 0)),
            "failures": len(payload.get("failed", [])),
            "message": ("Đang cập nhật học liệu theo từng phần. Bạn vẫn có thể sử dụng hệ thống."
                        if job.status == "running" else
                        payload.get("final_message", "Đã kết thúc lượt đồng bộ."))}


def step_incremental_sync(user):
    """Mỗi request tối đa một tài khoản hoặc một trang playlist (~50 video)."""
    job = YouTubeSyncJob.query.filter_by(user_id=user.id).first()
    if not job or job.status != "running":
        return incremental_sync_state(user)
    payload = json.loads(job.payload_json or "{}")
    if payload.get("accounts"):
        account_id = payload["accounts"].pop(0)
        credential = (db.session.get(ConnectedGoogleAccount, account_id)
                      if account_id is not None else None)
        if account_id is not None and (not credential or credential.user_id != user.id):
            payload["failed"].append("Một tài khoản đã được ngắt kết nối.")
        else:
            try:
                payload["tasks"].extend(_sync_channel_catalog(user, credential))
            except Exception as exc:
                db.session.rollback()
                label = credential.email if credential else user.email
                payload["failed"].append(f"{label}: {_friendly_sync_error(exc)}")
    elif payload.get("tasks"):
        task = payload["tasks"].pop(0)
        channel = db.session.get(YouTubeChannel, task["channel_pk"])
        credential = (db.session.get(ConnectedGoogleAccount, task["credential_pk"])
                      if task.get("credential_pk") else None)
        if not channel or channel.user_id != user.id or (credential and credential.user_id != user.id):
            payload["failed"].append("Một kênh đã ngừng được phép đồng bộ.")
        else:
            playlist = db.session.get(Playlist, task.get("playlist_pk")) if task.get("playlist_pk") else None
            playlist_youtube_id = task.get("uploads") or (playlist.youtube_playlist_id if playlist else None)
            if not playlist_youtube_id or (playlist and playlist.channel_id != channel.id):
                payload["failed"].append("Danh sách phát không hợp lệ hoặc đã bị xóa.")
            else:
                try:
                    page, seen = sync_playlist_page(user, channel, playlist_youtube_id,
                        credential=credential, page_token=task.get("page_token"),
                        seen_ids=task.get("seen"), uploads_playlist=bool(task.get("uploads")))
                    if page:
                        task["page_token"], task["seen"] = page, seen
                        payload["tasks"].insert(0, task)
                    else:
                        payload["completed_tasks"] += 1
                        all_seen = set(payload.get("seen_video_ids", []))
                        all_seen.update(seen)
                        payload["seen_video_ids"] = sorted(all_seen)
                        payload["videos_found"] = len(all_seen)
                        # Đồng bộ các học phần đã gán playlist khi một playlist hoàn tất.
                        _reconcile_course_playlist_assignments(user)
                except Exception as exc:
                    db.session.rollback()
                    payload["failed"].append(str(_friendly_sync_error(exc)))
    if not payload["accounts"] and not payload["tasks"]:
        job.status = "done"
        job.finished_at = utcnow()
        if payload["videos_found"]:
            payload["final_message"] = (f"Đã đồng bộ {payload['videos_found']} video học liệu hợp lệ; "
                                        f"{len(payload['failed'])} phần chưa đồng bộ được.")
        elif payload["failed"]:
            payload["final_message"] = ("Chưa xác minh được video học liệu vì có bước kết nối "
                                        "YouTube gặp lỗi. Hãy kiểm tra quyền truy cập và chọn Đồng bộ lại.")
        else:
            payload["final_message"] = ("Đã kiểm tra kênh và playlist nhưng chưa tìm thấy video học liệu "
                                        "có thể phát. Hãy tạo playlist thông thường chứa video "
                                        "công khai, cho phép nhúng và đồng bộ lại.")
    job.payload_json = json.dumps(payload, ensure_ascii=False)
    job.updated_at = utcnow()
    db.session.commit()
    return incremental_sync_state(user)

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
