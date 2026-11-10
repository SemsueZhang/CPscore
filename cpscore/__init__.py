"""CPscore's shared, dependency-free scoring protocol and tools."""

__version__ = "0.3.0"

from .scoring import make_report, score_report
from .schema import ReportValidationError, validate_report

__all__ = ["__version__", "make_report", "score_report", "validate_report", "ReportValidationError"]
