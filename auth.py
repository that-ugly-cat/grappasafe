import bcrypt
from fastapi import Request
from db import get_user_by_id


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def get_current_user(request: Request):
    data = request.session.get("user")
    if not data:
        return None
    return get_user_by_id(data["id"])


def require_auth(request: Request):
    user = get_current_user(request)
    if not user:
        from fastapi.responses import RedirectResponse
        return None, RedirectResponse("/", status_code=303)
    return user, None


def require_admin(request: Request):
    user = get_current_user(request)
    if not user:
        from fastapi.responses import RedirectResponse
        return None, RedirectResponse("/", status_code=303)
    if user["role"] != "admin":
        from fastapi.responses import JSONResponse
        return None, JSONResponse({"error": "forbidden"}, status_code=403)
    return user, None


def require_viewer(request: Request):
    """Read access to the monitoring pages: admins and observers."""
    user = get_current_user(request)
    if not user:
        from fastapi.responses import RedirectResponse
        return None, RedirectResponse("/", status_code=303)
    if user["role"] not in ("admin", "observer"):
        from fastapi.responses import JSONResponse
        return None, JSONResponse({"error": "forbidden"}, status_code=403)
    return user, None
