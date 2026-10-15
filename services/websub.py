from __future__ import annotations

from datetime import timedelta
import secrets
import requests
from flask import current_app, request, has_request_context
from defusedxml import ElementTree as ET

from models import db, HubSubscription, HubEvent, ErrorLog, utcnow

HUB_URL = "https://pubsubhubbub.appspot.com/subscribe"


def _base_url():
    configured = current_app.config.get("BASE_URL")
    if configured:
        return configured.rstrip("/")
    if has_request_context():
        return request.url_root.rstrip("/")
    raise RuntimeError("BASE_URL phải được cấu hình để gia hạn WebSub ngoài request.")


def subscribe_channel(channel):
    topic = f"https://www.youtube.com/xml/feeds/videos.xml?channel_id={channel.channel_id}"
    sub = HubSubscription.query.filter_by(channel_id=channel.id).first()
    if not sub:
        sub = HubSubscription(
            channel_id=channel.id,
            topic_url=topic,
            callback_url="",
            callback_secret=secrets.token_urlsafe(24),
        )
        db.session.add(sub)
        db.session.flush()
    callback = f"{_base_url()}/websub/callback/{channel.channel_id}/{sub.callback_secret}"
    sub.topic_url = topic
    sub.callback_url = callback
    sub.last_subscribed_at = utcnow()
    db.session.commit()

    resp = requests.post(
        HUB_URL,
        data={
            "hub.mode": "subscribe",
            "hub.topic": topic,
            "hub.callback": callback,
            "hub.verify": "async",
        },
        timeout=20,
    )
    if not resp.ok:
        db.session.add(ErrorLog(module="websub", message=f"Đăng ký Hub lỗi {resp.status_code}", details=resp.text[:10000]))
        db.session.commit()
        resp.raise_for_status()
    return sub


def verify_callback(channel, secret, args):
    sub = HubSubscription.query.filter_by(channel_id=channel.id, callback_secret=secret).first()
    if not sub:
        return None
    mode = args.get("hub.mode")
    topic = args.get("hub.topic")
    challenge = args.get("hub.challenge")
    lease_seconds = args.get("hub.lease_seconds")
    if mode not in ("subscribe", "unsubscribe") or topic != sub.topic_url or not challenge:
        return None
    if mode == "subscribe":
        sub.verified = True
        sub.last_verified_at = utcnow()
        if lease_seconds:
            try:
                sub.lease_seconds = int(lease_seconds)
                sub.lease_expires_at = utcnow() + timedelta(seconds=sub.lease_seconds)
            except Exception:
                pass
    else:
        sub.verified = False
    db.session.commit()
    return challenge


def parse_notification(channel, raw_body: bytes):
    text = raw_body.decode("utf-8", errors="replace")
    video_id = None
    event_type = "notification"
    try:
        root = ET.fromstring(raw_body)
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "yt": "http://www.youtube.com/xml/schemas/2015",
            "at": "http://purl.org/atompub/tombstones/1.0",
        }
        node = root.find(".//yt:videoId", ns)
        if node is not None and node.text:
            video_id = node.text.strip()
        deleted = root.find(".//at:deleted-entry", ns)
        if deleted is not None:
            event_type = "deleted"
            if not video_id:
                ref = deleted.attrib.get("ref", "")
                if ref.startswith("yt:video:"):
                    video_id = ref.split(":")[-1]
    except Exception as exc:
        db.session.add(ErrorLog(module="websub", message="Không phân tích được payload Hub", details=str(exc)))
    evt = HubEvent(
        channel_id=channel.id,
        youtube_video_id=video_id,
        event_type=event_type,
        raw_payload=text[:50000],
        processed=False,
    )
    db.session.add(evt)
    db.session.commit()
    return evt


def renew_expiring_subscriptions(hours=24):
    """Gia hạn các đăng ký WebSub sắp hết hạn. Yêu cầu BASE_URL được cấu hình."""
    from datetime import timedelta
    threshold = utcnow() + timedelta(hours=hours)
    renewed = 0
    for sub in HubSubscription.query.all():
        if (not sub.verified) or (sub.lease_expires_at is None) or (sub.lease_expires_at <= threshold):
            subscribe_channel(sub.channel)
            renewed += 1
    return renewed
