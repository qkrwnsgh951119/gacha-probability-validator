"""가챠 확률 검증 도구."""

from .lotto import LottoBox, Prize, SimulationResult, simulate
from .stats import RateTestResult, test_rate

__all__ = [
    "LottoBox",
    "Prize",
    "RateTestResult",
    "SimulationResult",
    "simulate",
    "test_rate",
]
__version__ = "0.1.0"
