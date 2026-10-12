"""Restaurant Billing & Management System: Flask application factory and entry point."""
import os
import secrets
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException

import db
from routes import admin, auth, orders, reports
from utils import ApiError

BASE_DIR = Path(__file__).resolve().parent


def _persistent_secret(instance_path):
    """Use SECRET_KEY from the environment, else generate one once and keep it on disk."""
    path = Path(instance_path) / "secret_key"
    if not path.exists():
        path.write_text(secrets.token_hex(32))
    return path.read_text().strip()


def create_app(config=None):
    app = Flask(__name__, static_folder="static", static_url_path="/static",
                instance_path=str(BASE_DIR / "instance"))
    Path(app.instance_path).mkdir(exist_ok=True)
    app.config.update(
        DATABASE=str(Path(app.instance_path) / "restaurant.db"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        MAX_CONTENT_LENGTH=1_000_000,
    )
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or _persistent_secret(app.instance_path)
    if config:
        app.config.update(config)

    db.init_app(app)
    for module in (auth, admin, orders, reports):
        app.register_blueprint(module.bp)

    @app.get("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    @app.errorhandler(ApiError)
    def handle_api_error(error):
        return jsonify(error=error.message), error.status

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        if request.path.startswith("/api/"):
            return jsonify(error=error.description), error.code
        return error

    @app.errorhandler(Exception)
    def handle_unexpected(error):
        app.logger.exception("Unhandled error")
        return jsonify(error="Something went wrong on the server. Please try again."), 500

    return app


if __name__ == "__main__":
    create_app().run(host=os.environ.get("HOST", "127.0.0.1"),
                     port=int(os.environ.get("PORT", 5000)), debug=False)
