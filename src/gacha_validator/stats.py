"""공시 확률 대비 관측 결과의 통계 검정."""

from dataclasses import dataclass

from scipy import stats


@dataclass(frozen=True)
class RateTestResult:
    pulls: int
    hits: int
    advertised_rate: float
    observed_rate: float
    p_value: float
    ci_low: float
    ci_high: float

    def is_consistent(self, alpha: float = 0.05) -> bool:
        """유의수준 alpha에서 공시 확률을 기각하지 못하면 True."""
        return self.p_value >= alpha


def test_rate(
    pulls: int,
    hits: int,
    advertised_rate: float,
    confidence: float = 0.95,
) -> RateTestResult:
    """정확 이항검정(양측)으로 관측 당첨 수가 공시 확률과 맞는지 검정한다."""
    if pulls <= 0:
        raise ValueError("pulls는 1 이상이어야 합니다.")
    if not 0 <= hits <= pulls:
        raise ValueError("hits는 0 이상 pulls 이하여야 합니다.")
    if not 0 < advertised_rate < 1:
        raise ValueError("advertised_rate는 0과 1 사이여야 합니다.")

    result = stats.binomtest(hits, pulls, advertised_rate, alternative="two-sided")
    ci = result.proportion_ci(confidence_level=confidence, method="exact")
    return RateTestResult(
        pulls=pulls,
        hits=hits,
        advertised_rate=advertised_rate,
        observed_rate=hits / pulls,
        p_value=result.pvalue,
        ci_low=ci.low,
        ci_high=ci.high,
    )
