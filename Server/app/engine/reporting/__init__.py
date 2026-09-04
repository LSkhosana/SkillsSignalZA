"""Readiness report assembly.

Report generation belongs here, not in HTTP handlers. The builders consume
a completed canonical assessment_result and do not rescore.
"""

from app.engine.reporting.outcomes import (
    PREVIEW_SCHEMA_VERSION,
    REPORT_SCHEMA_VERSION,
    REPORT_VERSION,
    REPORTING_VERSION,
)
from app.engine.reporting.preview import build_readiness_preview
from app.engine.reporting.report import build_readiness_report

__all__ = [
    "PREVIEW_SCHEMA_VERSION",
    "REPORT_SCHEMA_VERSION",
    "REPORT_VERSION",
    "REPORTING_VERSION",
    "build_readiness_preview",
    "build_readiness_report",
]
