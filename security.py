import base64
import hashlib
import json
from cryptography.fernet import Fernet
from flask import current_app


def _fernet():
    secret = current_app.config["SECRET_KEY"].encode("utf-8")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
    return Fernet(key)


def encrypt_json(data: dict) -> str:
    raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
    return _fernet().encrypt(raw).decode("utf-8")


def decrypt_json(value: str) -> dict:
    raw = _fernet().decrypt(value.encode("utf-8"))
    return json.loads(raw.decode("utf-8"))
