"""RFC 6238 TOTP (30s, 6 digits, SHA1) — compatible with Google/Microsoft Authenticator."""
import base64, hmac, hashlib, os, struct, time
from urllib.parse import quote

def new_secret() -> str:
    return base64.b32encode(os.urandom(20)).decode().rstrip("=")

def _code(secret: str, counter: int) -> str:
    key = base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)
    h = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    o = h[-1] & 15
    return f"{(struct.unpack('>I', h[o:o + 4])[0] & 0x7FFFFFFF) % 1000000:06d}"

def now_code(secret: str, at: float | None = None) -> str:
    return _code(secret, int((at or time.time()) // 30))

def verify(secret: str, code: str, window: int = 1, at: float | None = None) -> bool:
    code = (code or "").strip().replace(" ", "")
    if not secret or len(code) != 6 or not code.isdigit(): return False
    c = int((at or time.time()) // 30)
    return any(hmac.compare_digest(_code(secret, c + d), code) for d in range(-window, window + 1))

def uri(secret: str, email: str, issuer: str = "Neurealm Service Desk") -> str:
    return f"otpauth://totp/{quote(issuer)}:{quote(email)}?secret={secret}&issuer={quote(issuer)}&digits=6&period=30"
