"""Assessment HTTP boundary.

Future routes will accept assessment requests and return reports. They
must validate transport concerns only. Scoring rules belong in
`app.engine.scoring` and stable concepts belong in `app.domain`.
No endpoints are exposed in this scaffold.
"""

from fastapi import APIRouter

router = APIRouter()
