import hmac
import os

from ninja.security import APIKeyHeader, HttpBearer
from core.utils.jwt import decode_access_token
from core.models import User

class JWTAuth(HttpBearer):
    def authenticate(self, request, token):
        payload = decode_access_token(token)
        if not payload:
            return None
        try:
            # Querying directly returns an instantiated User model instance,
            # which skips Django's lazy-loading middleware entirely
            return User.objects.get(id=payload.get("user_id"))
        except User.DoesNotExist:
            return None


class TelegramBotAuth(APIKeyHeader):
    """
    Server-to-server auth for the Telegram bot: the bot must send the shared
    secret from TELEGRAM_BOT_SECRET in the X-Bot-Secret header.
    If the secret is not configured, every request is rejected.
    """
    param_name = "X-Bot-Secret"

    def authenticate(self, request, key):
        secret = os.getenv("TELEGRAM_BOT_SECRET", "")
        if secret and key and hmac.compare_digest(key, secret):
            return True
        return None