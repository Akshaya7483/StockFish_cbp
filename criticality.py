from enum import Enum


class Criticality(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"
    CRITICAL = "critical"


# Ascending order of importance; index + 1 gives a comparable rank.
_ORDER = [
    Criticality.LOW,
    Criticality.MEDIUM,
    Criticality.HIGH,
    Criticality.VERY_HIGH,
    Criticality.CRITICAL,
]


def rank(criticality: Criticality) -> int:
    """Comparable integer rank (LOW=1 .. CRITICAL=5)."""
    return _ORDER.index(criticality) + 1
