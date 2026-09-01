"""Quality checks for assessment outputs.

Deterministic Contract 1.2 assessment QA runs before a completed score
is released. Extraction and report rendering remain out of scope.
"""

from app.engine.qa.assessment import band_for, run_assessment_qa

__all__ = ["band_for", "run_assessment_qa"]
