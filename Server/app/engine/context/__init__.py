"""Scoring-context assembly.

Package J binds accepted evidence facts onto Rubric V2 criteria. It does not
award points or call the scoring engine.
"""

from app.engine.context.assembly import assemble_scoring_context
from app.engine.context.outcomes import ASSEMBLER_VERSION

__all__ = ["ASSEMBLER_VERSION", "assemble_scoring_context"]
