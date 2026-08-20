# Flask app entry point — registers API routes and serves the frontend.
from flask import Flask

from backend.api.routes import api_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(api_bp)
    return app


if __name__ == "__main__":
    create_app().run(debug=True, port=5000)
