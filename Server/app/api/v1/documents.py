"""Document HTTP boundary.

Future routes will handle candidate document metadata after an upload
pipeline exists. Parsing, storage and virus scanning do not belong in
this module. No endpoints are exposed in this scaffold.
"""

from fastapi import APIRouter

router = APIRouter()
