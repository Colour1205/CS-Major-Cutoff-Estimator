# Flask app entry point — registers API routes and serves the frontend.
from flask import Flask

from backend.api.routes import api_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(api_bp)

    # The frontend is a static page opened separately from this API (a
    # different origin), so it needs CORS to be able to fetch from here.
    @app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
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
