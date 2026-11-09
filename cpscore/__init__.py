"""CPScore's shared, dependency-free review protocol and scoring engine."""

__version__ = "0.2.0"

from .scoring import make_report, score_report
from .schema import ReportValidationError, validate_report

__all__ = ["__version__", "make_report", "score_report", "validate_report", "ReportValidationError"]
