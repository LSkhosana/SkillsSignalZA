"""Safe candidate-submitted link retrieval."""

from app.engine.extraction.links.service import retrieve_candidate_link
from app.engine.extraction.links.url import normalize_submitted_url

__all__ = ["normalize_submitted_url", "retrieve_candidate_link"]
