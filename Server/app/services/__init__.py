"""Use-case services.

Services coordinate API input, domain rules, engine work and
repositories. They keep HTTP handlers thin and prevent scoring rules
from leaking into routes.
"""

from app.services.assessment_scoring import score_frozen_assessment

__all__ = ["score_frozen_assessment"]
