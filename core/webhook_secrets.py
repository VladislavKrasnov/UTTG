import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from core.settings import settings


def _fernet() -> Fernet:
    source = settings.webhook_encryption_key
    if not source:
        raise RuntimeError("UTTG_WEBHOOK_ENCRYPTION_KEY is required")
    key = base64.urlsafe_b64encode(hashlib.sha256(source.encode()).digest())
    return Fernet(key)


def encrypt_webhook_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def decrypt_webhook_secret(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Webhook signing secret cannot be decrypted") from exc
