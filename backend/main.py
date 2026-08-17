"""main.py — Orbit backend entrypoint.

App + endpoints live in routes.py; this file only provides the module uvicorn
starts from and an optional `python main.py` dev run.
"""

import uvicorn

from routes import app  # noqa: F401  (re-exported for `uvicorn main:app`)

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)