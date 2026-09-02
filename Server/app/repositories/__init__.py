"""Persistence boundary.

Callers depend on vendor-neutral AssessmentRepository and DocumentStorage
ports. PostgreSQL and Supabase Storage adapters implement those ports.
"""

from app.repositories.interfaces import AssessmentRepository, DocumentStorage
from app.repositories.postgres import PostgresAssessmentRepository
from app.repositories.supabase import SupabaseDocumentStorage

__all__ = [
    "AssessmentRepository",
    "DocumentStorage",
    "PostgresAssessmentRepository",
    "SupabaseDocumentStorage",
]
