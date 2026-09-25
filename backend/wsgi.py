# Production entry point for gunicorn (see Dockerfile) — the same startup
# `python -m backend.app` does, minus Flask's dev server.
#
# Must run as a single gunicorn worker process: the background refresh
# threads started here would otherwise run once per worker, all writing
# the same files, and each worker would get its own random SECRET_KEY
# fallback (admin sessions only valid on whichever worker issued them).
import os
import shutil
from pathlib import Path

from werkzeug.middleware.proxy_fix import ProxyFix

from backend.app import create_app
from backend.config import GRADES_DB_PATH
from backend.services.backtest import start_background_backtest_refresh
from backend.services.enrollment import start_background_refresh


def seed_data_dir(seed_dir: str, data_dir: str = str(Path(GRADES_DB_PATH).parent)) -> None:
    """In the container, backend/data is a persistent volume mounted over
    the image's own copy, so it starts out empty. Copy in the seed files the
    image was built with (kept at SEED_DATA_DIR) -- but only ones that don't
    exist yet, so runtime state (admin edits, refreshed enrollment data,
    grades.db) survives restarts and redeploys instead of being reset.
    """
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    for seed_file in Path(seed_dir).iterdir():
        target = Path(data_dir) / seed_file.name
        if seed_file.is_file() and not target.exists():
            shutil.copy2(seed_file, target)
            print(f"[seed] copied {seed_file.name} into {data_dir}")


if os.environ.get("SEED_DATA_DIR"):
    seed_data_dir(os.environ["SEED_DATA_DIR"])

start_background_refresh()
start_background_backtest_refresh()
app = create_app()

# Behind a Kubernetes Ingress, request.remote_addr is the ingress
# controller, not the visitor -- every submission would get the same
# ip_hash, breaking the admin dashboard's same-source flag. Set this to the
# number of trusted proxies in front of the app (1 for a plain Ingress).
# Leave it at 0 if the app is exposed directly, or clients could spoof
# X-Forwarded-For.
proxy_hops = int(os.environ.get("PROXY_FIX_HOPS", "0"))
if proxy_hops:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=proxy_hops, x_proto=proxy_hops)
