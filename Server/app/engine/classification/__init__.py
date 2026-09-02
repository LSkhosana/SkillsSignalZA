"""Higher-order evidence classification.

Package I appends Contract 1.2 project/work/role/document-quality facts to a
Package H bundle. It does not bind criteria or award points.
"""

from app.engine.classification.higher_order import classify_higher_order_evidence
from app.engine.classification.outcomes import CLASSIFIER_VERSION

__all__ = ["CLASSIFIER_VERSION", "classify_higher_order_evidence"]
