# Flask app entry point — registers API routes and serves the frontend.
import os
import secrets

from flask import Flask

from backend.api.admin_routes import admin_bp
from backend.api.routes import api_bp


def create_app() -> Flask:
    from backend.services.migrate_scraped_grades import run as migrate_scraped_grades

    # Idempotent (skips a year that already has scraped_grades rows), so
    # this is safe to run on every startup -- keeps a fresh clone/database
    # seeded with the historical data without a manual migration step.
    migrate_scraped_grades()

    app = Flask(__name__)
    app.register_blueprint(api_bp)
    app.register_blueprint(admin_bp)

    # Needed for the admin login session. Falls back to a random key if
    # unset -- fine for this single-process dev server, but it means
    # sessions won't survive a restart. Set SECRET_KEY for a stable one.
    app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
    if not os.environ.get("ADMIN_PASSWORD"):
        print("[warning] ADMIN_PASSWORD is not set -- /admin login will always fail.")

    # The frontend is a static page opened separately from this API (a
    # different origin), so it needs CORS to be able to fetch from here.
    # POST requests with a JSON body trigger a preflight OPTIONS request,
    # which needs Allow-Methods/Allow-Headers too, not just Allow-Origin,
    # or the browser blocks the real request before it's even sent.
    @app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return response

    return app


if __name__ == "__main__":
    from backend.services.backtest import start_background_backtest_refresh
    from backend.services.enrollment import start_background_refresh

    # Keeps enrollment_data.csv current without a manual re-run — picks up
    # newly-published real data (replacing any forecasted columns) once a
    # day. use_reloader=False so Flask's debug reloader doesn't spawn a
    # second process that starts duplicate refresh threads.
    start_background_refresh()
    # Backtest is pure computation (no network calls), so it's cheap to
    # recompute more often — picks up edits to historical_averages.csv /
    # safe_grades.csv or newly-arrived enrollment data.
    start_background_backtest_refresh()
    create_app().run(debug=True, port=5000, use_reloader=False)
