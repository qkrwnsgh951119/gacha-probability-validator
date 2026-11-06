"""로또 상자 개봉 시뮬레이션과 등급별 확률 검증.

매 개봉은 독립시행이다(천장, 확률 변동 없음).
"""

import logging
import random
from dataclasses import dataclass

from .stats import RateTestResult, test_rate

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Prize:
    """상자 안의 내용물 한 종류."""

    name: str
    rate: float  # 0.01 == 1%


@dataclass(frozen=True)
class LottoBox:
    """여러 등급의 내용물을 가진 상자. 모든 확률의 합은 100%여야 한다."""

    name: str
    prizes: tuple[Prize, ...]

    def __post_init__(self) -> None:
        if not self.prizes:
            raise ValueError("상자에 내용물이 하나 이상 있어야 합니다.")
        names = [p.name for p in self.prizes]
        if len(names) != len(set(names)):
            raise ValueError(f"내용물 이름이 중복됩니다: {names}")
        for p in self.prizes:
            if not 0 < p.rate < 1:
                raise ValueError(f"{p.name}의 확률은 0%와 100% 사이여야 합니다: {p.rate:.4%}")
        total = sum(p.rate for p in self.prizes)
        if abs(total - 1) > 1e-9:
            raise ValueError(f"확률의 합이 100%가 아닙니다: {total:.4%}")

    def open(self, rng: random.Random) -> Prize:
        """상자를 한 번 열어 내용물 하나를 뽑는다."""
        return rng.choices(self.prizes, weights=[p.rate for p in self.prizes])[0]


@dataclass(frozen=True)
class PrizeStat:
    prize: Prize
    test: RateTestResult

    @property
    def expected_hits(self) -> float:
        return self.test.pulls * self.prize.rate


@dataclass(frozen=True)
class SimulationResult:
    box_name: str
    opens: int
    seed: int
    alpha: float
    stats: tuple[PrizeStat, ...]

    @property
    def per_prize_alpha(self) -> float:
        # 등급 여러 개를 동시에 검정하므로 본페로니 보정:
        # 정상 상자인데 "불일치"로 잘못 판정될 확률을 전체 alpha 이하로 묶는다.
        return self.alpha / len(self.stats)

    def is_consistent(self) -> bool:
        """모든 등급이 설정 확률과 통계적으로 맞으면 True."""
        return all(s.test.is_consistent(self.per_prize_alpha) for s in self.stats)


def simulate(
    box: LottoBox,
    opens: int = 1_000,
    seed: int | None = None,
    alpha: float = 0.01,
    show_first: int = 10,
    progress_every: int = 100,
    verbose: bool = True,
) -> SimulationResult:
    """상자를 opens번 열고, 등급별 결과가 설정 확률과 맞는지 검정해 로그로 남긴다.

    seed를 주지 않으면 매번 새로운 무작위 결과가 나온다. 사용한 seed는 로그에
    남으므로, 같은 seed를 넘기면 그 실행을 그대로 재현할 수 있다.
    verbose=False면 로그를 남기지 않는다.
    """
    if opens <= 0:
        raise ValueError("opens는 1 이상이어야 합니다.")
    if seed is None:
        seed = random.randrange(2**32)
    rng = random.Random(seed)
    log = logger.info if verbose else (lambda *args: None)

    log("")
    log("===== [%s] %s회 개봉 시작 (seed=%d) =====", box.name, f"{opens:,}", seed)
    log("설정 확률: %s", " | ".join(f"{p.name} {p.rate:.2%}" for p in box.prizes))

    counts = {p.name: 0 for p in box.prizes}
    for i in range(1, opens + 1):
        prize = box.open(rng)
        counts[prize.name] += 1
        if i <= show_first:
            log("  %4d번째 개봉 → %s", i, prize.name)
        elif i == show_first + 1:
            log("  ... (이후 개별 결과 생략, %s회마다 누적 집계) ...", progress_every)
        if i % progress_every == 0 or i == opens:
            log(
                "  [누적 %5s회] %s",
                f"{i:,}",
                " | ".join(f"{name} {c:>4}" for name, c in counts.items()),
            )

    stats = tuple(
        PrizeStat(p, test_rate(pulls=opens, hits=counts[p.name], advertised_rate=p.rate))
        for p in box.prizes
    )
    result = SimulationResult(box.name, opens, seed, alpha, stats)
    if verbose:
        _log_report(result)
    return result


def _log_report(result: SimulationResult) -> None:
    a = result.per_prize_alpha
    logger.info("")
    logger.info("----- 결과 요약 -----")
    # 한글은 화면에서 2칸을 차지해 % 포맷 폭이 어긋나므로 머리글은 직접 맞춘다.
    logger.info(
        "등급      설정확률    기대횟수    실제횟수    실제확률   95% 신뢰구간            p-value  판정"
    )
    for s in result.stats:
        t = s.test
        logger.info(
            "%-5s %10.2f%% %11.1f %11d %10.2f%%   %6.2f%% ~ %6.2f%%  %10.4f  %s",
            s.prize.name,
            s.prize.rate * 100,
            s.expected_hits,
            t.hits,
            t.observed_rate * 100,
            t.ci_low * 100,
            t.ci_high * 100,
            t.p_value,
            "정상" if t.is_consistent(a) else "불일치",
        )

    for s in result.stats:
        if s.expected_hits < 5:
            p_zero = (1 - s.prize.rate) ** result.opens
            logger.info(
                "※ %s: %s회 개봉 시 기대 횟수가 %.1f회뿐이라 한 번도 안 나올 확률도 %.1f%%입니다. "
                "이 등급을 제대로 검증하려면 개봉 횟수를 늘리세요.",
                s.prize.name, f"{result.opens:,}", s.expected_hits, p_zero * 100,
            )

    logger.info("")
    if result.is_consistent():
        logger.info(
            "최종 판정: 정상 ✅ 모든 등급이 설정 확률과 통계적으로 일치합니다. (α=%.2f, 등급별 α=%.4f)",
            result.alpha, a,
        )
    else:
        bad = ", ".join(s.prize.name for s in result.stats if not s.test.is_consistent(a))
        logger.info(
            "최종 판정: 불일치 ❌ %s 등급이 설정 확률에서 벗어났습니다. (α=%.2f, 등급별 α=%.4f, seed=%d)",
            bad, result.alpha, a, result.seed,
        )
