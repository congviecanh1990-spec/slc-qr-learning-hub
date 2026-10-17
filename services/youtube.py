from __future__ import annotations

from datetime import datetime, timezone
import requests
from flask import current_app

from models import db, OAuthAccount, YouTubeChannel, Playlist, Video, PlaylistVideo, Course, CourseVideo, CoursePlaylist, ErrorLog, utcnow
from security import decrypt_json, encrypt_json

YOUTUBE_API = "https://www.googleapis.com/youtube/v3"
TOKEN_URL = "https://oauth2.googleapis.com/token"


def _log_error(module, message, details=None):
    db.session.add(ErrorLog(module=module, message=message[:500], details=(details or "")[:10000]))
    db.session.commit()


def _token_for_user(user):
    account = OAuthAccount.query.filter_by(user_id=user.id).first()
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


def _get(user, path, params):
    access = _token_for_user(user)
    headers = {"Authorization": f"Bearer {access}"}
    resp = requests.get(f"{YOUTUBE_API}/{path}", params=params, headers=headers, timeout=30)
    if resp.status_code == 401:
        account = OAuthAccount.query.filter_by(user_id=user.id).first()
        token = decrypt_json(account.token_encrypted)
        token["expires_at"] = 0
        account.token_encrypted = encrypt_json(token)
        db.session.commit()
        access = _token_for_user(user)
        headers = {"Authorization": f"Bearer {access}"}
        resp = requests.get(f"{YOUTUBE_API}/{path}", params=params, headers=headers, timeout=30)
    if not resp.ok:
        _log_error("youtube_api", f"GET {path} lỗi {resp.status_code}", resp.text)
        resp.raise_for_status()
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


def sync_my_channel(user):
    data = _get(user, "channels", {"part": "snippet,contentDetails", "mine": "true", "maxResults": 50})
    items = data.get("items", [])
    if not items:
        raise RuntimeError("Không tìm thấy kênh YouTube thuộc tài khoản này.")

    synced = []
    for item in items:
        cid = item["id"]
        snippet = item.get("snippet", {})
        uploads = item.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
        channel = YouTubeChannel.query.filter_by(user_id=user.id, channel_id=cid).first()
        if not channel:
            channel = YouTubeChannel(user_id=user.id, channel_id=cid)
            db.session.add(channel)
        channel.title = snippet.get("title", cid)
        channel.uploads_playlist_id = uploads
        channel.thumbnail_url = _thumb(snippet)
        channel.last_synced_at = utcnow()
        db.session.flush()
        playlists = sync_playlists(user, channel)
        # Đồng bộ nội dung của từng playlist do giảng viên tạo để Web App có thể
        # gán playlist vào học phần và tạo QR playlist động.
        for playlist in playlists:
            sync_playlist_items(user, channel, playlist.youtube_playlist_id)
        if uploads:
            sync_playlist_items(user, channel, uploads, uploads_playlist=True)
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
                if not link.source_playlist_id:
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


def sync_playlists(user, channel):
    seen_ids = set()
    synced_playlists = []
    page = None
    while True:
        params = {"part": "snippet,status", "mine": "true", "maxResults": 50}
        if page:
            params["pageToken"] = page
        data = _get(user, "playlists", params)
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


def sync_playlist_items(user, channel, playlist_youtube_id, uploads_playlist=False):
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
        data = _get(user, "playlistItems", params)
        for item in data.get("items", []):
            vid = item.get("contentDetails", {}).get("videoId") or item.get("snippet", {}).get("resourceId", {}).get("videoId")
            if vid:
                video_ids.append(vid)
                item_meta[vid] = item
        page = data.get("nextPageToken")
        if not page:
            break

    for i in range(0, len(video_ids), 50):
        sync_video_ids(user, channel, video_ids[i:i + 50])

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
            if not video:
                continue
            current_video_ids.add(video.id)
            link = PlaylistVideo.query.filter_by(playlist_id=playlist.id, video_id=video.id).first()
            position = item_meta.get(vid, {}).get("snippet", {}).get("position")
            if not link:
                db.session.add(PlaylistVideo(playlist_id=playlist.id, video_id=video.id, position=position))
            else:
                link.position = position
        # Xóa liên kết đã bị gỡ khỏi playlist YouTube. Video vẫn được giữ trong kho
        # video nếu còn tồn tại trên kênh.
        for link in PlaylistVideo.query.filter_by(playlist_id=playlist.id).all():
            if link.video_id not in current_video_ids:
                db.session.delete(link)
    db.session.commit()


def sync_video_ids(user, channel, video_ids):
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
    )
    returned = set()
    for item in data.get("items", []):
        vid = item["id"]
        returned.add(vid)
        snippet = item.get("snippet", {})
        status = item.get("status", {})
        content = item.get("contentDetails", {})
        video = Video.query.filter_by(youtube_video_id=vid).first()
        if not video:
            video = Video(channel_id=channel.id, youtube_video_id=vid)
            db.session.add(video)
        video.channel_id = channel.id
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
        if video:
            video.is_available = False
            video.last_synced_at = utcnow()
    db.session.commit()


def reconcile_user(user):
    channels = YouTubeChannel.query.filter_by(user_id=user.id).all()
    total = 0
    for channel in channels:
        # Đối soát cả cấu trúc playlist để QR playlist phản ánh đúng video vừa thêm/gỡ.
        playlists = sync_playlists(user, channel)
        for playlist in playlists:
            sync_playlist_items(user, channel, playlist.youtube_playlist_id)
        if channel.uploads_playlist_id:
            sync_playlist_items(user, channel, channel.uploads_playlist_id, uploads_playlist=True)

        total += len(channel.videos)
        channel.last_synced_at = utcnow()
    db.session.commit()
    return total
