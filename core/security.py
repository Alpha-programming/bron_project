from ninja.security import HttpBearer
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