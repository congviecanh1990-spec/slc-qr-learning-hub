from __future__ import annotations

from datetime import datetime, timezone
import requests
from flask import current_app

from models import db, OAuthAccount, YouTubeChannel, Playlist, Video, PlaylistVideo, ErrorLog, utcnow
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
        sync_playlists(user, channel)
        if uploads:
            sync_playlist_items(user, channel, uploads, uploads_playlist=True)
        synced.append(channel)
    db.session.commit()
    return synced


def sync_playlists(user, channel):
    page = None
    while True:
        params = {"part": "snippet,status", "mine": "true", "maxResults": 50}
        if page:
            params["pageToken"] = page
        data = _get(user, "playlists", params)
        for item in data.get("items", []):
            pid = item["id"]
            snippet = item.get("snippet", {})
            p = Playlist.query.filter_by(youtube_playlist_id=pid).first()
            if not p:
                p = Playlist(channel_id=channel.id, youtube_playlist_id=pid)
                db.session.add(p)
            p.channel_id = channel.id
            p.title = snippet.get("title", pid)
            p.description = snippet.get("description")
            p.privacy_status = item.get("status", {}).get("privacyStatus")
            p.last_synced_at = utcnow()
        db.session.flush()
        page = data.get("nextPageToken")
        if not page:
            break


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
            last_synced_at=utcnow(),
        )
        db.session.add(playlist)
        db.session.flush()

    if playlist:
        for vid in video_ids:
            video = Video.query.filter_by(youtube_video_id=vid).first()
            if not video:
                continue
            link = PlaylistVideo.query.filter_by(playlist_id=playlist.id, video_id=video.id).first()
            if not link:
                position = item_meta.get(vid, {}).get("snippet", {}).get("position")
                db.session.add(PlaylistVideo(playlist_id=playlist.id, video_id=video.id, position=position))
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
        ids = [v.youtube_video_id for v in channel.videos]
        for i in range(0, len(ids), 50):
            sync_video_ids(user, channel, ids[i:i + 50])
            total += len(ids[i:i + 50])
        channel.last_synced_at = utcnow()
    db.session.commit()
    return total
