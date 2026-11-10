"""Shared protocol constants for coverage and finding classifications."""

SCHEMA_VERSION = "3.0"
OBJECTS = ("statement", "solution", "editorial")
COVERAGE_ITEMS = {
    "statement": ("definition", "io", "constraints", "boundaries", "samples"),
    "solution": ("algorithm", "correctness", "complexity", "implementation"),
    "editorial": ("claims", "reasoning", "proof", "complexity"),
}
COMPLETE_COVERAGE_STATUSES = frozenset(("checked", "not_applicable"))
RULE_SEVERITIES = {
    "incorrect_sample": "fatal",
    "wrong_answer": "fatal",
    "invalid_algorithm": "fatal",
    # A defective proof of an independently valid algorithm is not a WA.
    "invalid_proof": "major",
    "ambiguous_answer": "fatal",
    "incomplete_explanation": ("major", "minor"),
    "quality_defect": "major",
    "local_presentation": "minor",
    "other": None,
}
INITIAL_SCORE = 10
PASS_THRESHOLD = 6
RECOMMEND_THRESHOLD = 9
PENALTIES = {"fatal": 10, "major": 3, "minor": 1}
STATUS_PRIORITY = {"resolved": 0, "suspected": 1, "confirmed": 2}
