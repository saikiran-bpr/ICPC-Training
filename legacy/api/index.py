"""
Vercel Python serverless entry point.

Vercel's @vercel/python builder looks for `app` (or `handler`) in the imported
module. We import the Flask `app` from the project root and re-export it so
every HTTP request is routed through the existing WSGI app.

Static files under /static/* are served by Flask itself (the app was created
with `static_url_path="/static"`), so the catch-all route in vercel.json sends
every path here.
"""

import sys
from pathlib import Path

# Make the project root importable from the api/ subfolder.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import app  # noqa: E402  (path setup must happen first)

# Vercel auto-detects `app` as the WSGI entry; expose `handler` too as a
# defensive alias in case the auto-detection picks the other name.
handler = app
