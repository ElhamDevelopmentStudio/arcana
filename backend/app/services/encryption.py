from __future__ import annotations

import hashlib
import hmac
import os
from typing import Any

from sqlalchemy.types import LargeBinary, TypeDecorator

from app.config import get_settings

_MAGIC_PREFIX = b"NIPE_ENC_V1|"
_NONCE_SIZE = 16
_TAG_SIZE = hashlib.sha256().digest_size


def _active_encryption_enabled() -> bool:
    settings = get_settings()
    if not settings.saas_mode:
        return False
    if not settings.data_encryption_key:
        raise RuntimeError("SAAS_MODE is enabled but DATA_ENCRYPTION_KEY is missing.")
    return True


def _encryption_key() -> bytes:
    settings = get_settings()
    raw_key = (settings.data_encryption_key or "").strip()
    return hashlib.sha256(raw_key.encode("utf-8")).digest()


def _as_bytes(value: Any) -> bytes:
    if value is None:
        return b""
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, str):
        return value.encode("utf-8")
    if hasattr(value, "tobytes"):
        return value.tobytes()
    return str(value).encode("utf-8")


def _xor_bytes(source: bytes, secret: bytes) -> bytes:
    return bytes(byte ^ key for byte, key in zip(source, secret))


def _keystream(secret: bytes, nonce: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        chunk = hmac.new(secret, nonce + counter.to_bytes(4, "big"), hashlib.sha256).digest()
        out.extend(chunk)
        counter += 1
    return bytes(out[:length])


def _encrypt_bytes(plaintext: bytes) -> bytes:
    if not _active_encryption_enabled():
        return plaintext

    key = _encryption_key()
    nonce = os.urandom(_NONCE_SIZE)
    pad = _keystream(key, nonce, len(plaintext))
    ciphertext = _xor_bytes(plaintext, pad)
    digest = hmac.new(key, nonce + ciphertext, hashlib.sha256).digest()
    return _MAGIC_PREFIX + nonce + digest + ciphertext


def _decrypt_bytes(payload: bytes) -> bytes:
    if not _active_encryption_enabled():
        return payload

    if not payload.startswith(_MAGIC_PREFIX):
        return payload

    payload_body = payload[len(_MAGIC_PREFIX) :]
    if len(payload_body) < _NONCE_SIZE + _TAG_SIZE:
        raise RuntimeError("Encrypted payload appears corrupted.")

    nonce = payload_body[:_NONCE_SIZE]
    tag = payload_body[_NONCE_SIZE : _NONCE_SIZE + _TAG_SIZE]
    ciphertext = payload_body[_NONCE_SIZE + _TAG_SIZE :]

    key = _encryption_key()
    expected = hmac.new(key, nonce + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(tag, expected):
        raise RuntimeError("Encrypted payload failed integrity check.")

    pad = _keystream(key, nonce, len(ciphertext))
    return _xor_bytes(ciphertext, pad)


class EncryptedText(TypeDecorator):
    impl = LargeBinary
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: Any) -> bytes | None:
        if value is None:
            return None
        return _encrypt_bytes(_as_bytes(value))

    def process_result_value(self, value: bytes | None, dialect: Any) -> str | None:
        if value is None:
            return None
        payload = _as_bytes(value)
        return _decrypt_bytes(payload).decode("utf-8")


class EncryptedBinary(TypeDecorator):
    impl = LargeBinary
    cache_ok = True

    def process_bind_param(self, value: bytes | bytearray | str | None, dialect: Any) -> bytes | None:
        if value is None:
            return None
        return _encrypt_bytes(_as_bytes(value))

    def process_result_value(self, value: bytes | bytearray | memoryview | None, dialect: Any) -> bytes | None:
        if value is None:
            return None
        payload = _as_bytes(value)
        return _decrypt_bytes(payload)
