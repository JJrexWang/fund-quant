import hashlib, hmac, os, secrets
import jwt
from datetime import datetime, timedelta, timezone

SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
ALGO = "HS256"

def hash_password(pw: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 200_000)
    return f"{salt}${dk.hex()}"

def verify_password(pw: str, stored: str) -> bool:
    try:
        salt, hexdk = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 200_000)
        return hmac.compare_digest(dk.hex(), hexdk)
    except Exception:
        return False

def make_token(username: str, role: str) -> str:
    payload = {"sub": username, "role": role, "exp": datetime.now(timezone.utc) + timedelta(days=7)}
    return jwt.encode(payload, SECRET, algorithm=ALGO)

def parse_token(token: str):
    return jwt.decode(token, SECRET, algorithms=[ALGO])

def gen_api_key():
    raw = "fqk_" + secrets.token_urlsafe(32)
    return raw, raw[:12], hashlib.sha256(raw.encode()).hexdigest()

def hash_api_key(raw: str) -> str:
    return hashlib.sha256((raw or "").encode()).hexdigest()
