"""Report HTTP boundary.

Future routes will fetch generated readiness reports. Report assembly
belongs in `app.engine.reporting`, not in HTTP handlers. No endpoints
are exposed in this scaffold.
"""

from fastapi import APIRouter

router = APIRouter()
