"""Sign-in, sign-out and the role-check decorator."""
from functools import wraps

from flask import Blueprint, jsonify, session
from werkzeug.security import check_password_hash

from db import get_db
from utils import ApiError, clean_str, json_body

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def login_required(role=None):
    """Require a signed-in user; pass role='admin' to restrict to admins."""

    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if not session.get("user_id"):
                raise ApiError("Please sign in to continue.", 401)
            if role and session.get("role") != role:
                raise ApiError("Only an admin can do this.", 403)
            return view(*args, **kwargs)

        return wrapper

    return decorator


def _public_user():
    return {"id": session["user_id"], "name": session["name"], "role": session["role"]}


@bp.post("/login")
def login():
    data = json_body()
    username = clean_str(data.get("username"), "Username", 50, required=True)
    password = data.get("password")
    if not isinstance(password, str) or not password:
        raise ApiError("Password is required.")
    user = get_db().execute(
        "SELECT * FROM users WHERE username = ? AND active = 1", (username,)
    ).fetchone()
    if user is None or not check_password_hash(user["password_hash"], password):
        raise ApiError("Wrong username or password.", 401)
    session.clear()
    session.update(user_id=user["id"], role=user["role"], name=user["name"])
    return jsonify(user=_public_user())


@bp.post("/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@bp.get("/me")
@login_required()
def me():
    return jsonify(user=_public_user())
