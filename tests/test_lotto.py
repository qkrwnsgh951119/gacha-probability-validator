import logging
import random

import pytest

from gacha_validator import test_rate as rate_test
from gacha_validator.lotto import LottoBox, Prize, simulate

# ── 기획 설정: 여기 값을 바꾸면 테스트에 바로 반영됩니다 ──
LOTTO_TEST = LottoBox(
    name="Lotto Test",
    prizes=(
        Prize("1등", 0.01),   # 1%
        Prize("2등", 0.10),   # 10%
        Prize("3등", 0.889),  # 88.9%
        Prize("4등", 0.001),  # 0.1%
    ),
)
OPENS = 1_000


def test_lotto_box_matches_configured_rates():
    """Lotto Test를 1,000번 열어 등급별 결과가 설정 확률대로 나오는지 검증한다.

    실행할 때마다 결과가 달라진다. 정상 상자라도 약 1% 확률로 우연히 불일치가
    나올 수 있으며, 그때는 로그의 seed로 같은 결과를 재현할 수 있다.
    """
    result = simulate(LOTTO_TEST, opens=OPENS)

    assert sum(s.test.hits for s in result.stats) == OPENS
    assert result.is_consistent(), f"설정 확률과 불일치 (seed={result.seed})"


def test_same_seed_gives_same_result():
    """같은 seed로 두 번 돌리면 결과가 똑같아야 한다. (로그는 생략)"""
    a = simulate(LOTTO_TEST, opens=OPENS, seed=42, verbose=False)
    b = simulate(LOTTO_TEST, opens=OPENS, seed=42, verbose=False)
    assert [s.test.hits for s in a.stats] == [s.test.hits for s in b.stats]


def test_rigged_box_is_detected():
    """실제로는 1등이 0.3%만 나오는 조작된 상자를, 1% 상자로 검증하면 불일치로 잡아내야 한다."""
    rigged = LottoBox(
        "조작된 상자",
        (Prize("1등", 0.003), Prize("2등", 0.10), Prize("3등", 0.896), Prize("4등", 0.001)),
    )
    rng = random.Random(7)
    opens = 20_000
    first_hits = sum(rigged.open(rng).name == "1등" for _ in range(opens))

    # 공지 확률(1%)과 비교
    check = rate_test(pulls=opens, hits=first_hits, advertised_rate=0.01)
    logging.getLogger(__name__).info(
        "[조작된 상자] 1등 %d/%d회 (%.2f%%), 공지 1%% 대비 p-value=%.2e → %s",
        first_hits, opens, check.observed_rate * 100, check.p_value,
        "정상" if check.is_consistent(0.01) else "불일치 탐지 ✅",
    )
    assert not check.is_consistent(alpha=0.01)


def test_each_open_is_independent():
    """매 개봉이 독립시행인지 확인한다.

    1) 직전에 X가 나왔어도 다음에 X가 나올 확률은 그대로여야 한다. (연속 당첨 보정 없음)
    2) 1등이 100번 넘게 안 나왔어도 다음 1등 확률은 그대로 1%여야 한다. (천장/보정 없음)
    표본을 충분히 모으려고 20만 번 연다. (seed 고정: 매번 같은 결과로 검증)
    """
    log = logging.getLogger(__name__)
    opens = 200_000
    rng = random.Random(2026)
    results = [LOTTO_TEST.open(rng).name for _ in range(opens)]
    pairs = list(zip(results, results[1:]))  # (직전 결과, 다음 결과)

    log.info("")
    log.info("===== [독립시행 검증] %s회 개봉 =====", f"{opens:,}")
    for prize in LOTTO_TEST.prizes:
        after_same = [nxt for prev, nxt in pairs if prev == prize.name]
        hits = sum(nxt == prize.name for nxt in after_same)
        r = rate_test(pulls=len(after_same), hits=hits, advertised_rate=prize.rate)
        log.info(
            "직전 %s → 다음도 %s: %d/%d회 (%.2f%%, 설정 %.2f%%) → %s",
            prize.name, prize.name, hits, len(after_same),
            r.observed_rate * 100, prize.rate * 100,
            "독립 ✅" if r.is_consistent(0.01) else "의존 의심 ❌",
        )
        assert r.is_consistent(alpha=0.01), f"{prize.name} 직후 확률이 달라짐"

    # 1등이 100번 이상 연속으로 안 나온 직후의 1등 확률
    streak, trials, hits = 0, 0, 0
    for name in results:
        if streak >= 100:
            trials += 1
            hits += name == "1등"
        streak = 0 if name == "1등" else streak + 1
    r = rate_test(pulls=trials, hits=hits, advertised_rate=0.01)
    log.info(
        "1등 100연속 미당첨 직후 1등: %d/%d회 (%.2f%%, 설정 1.00%%) → %s",
        hits, trials, r.observed_rate * 100,
        "보정 없음 ✅" if r.is_consistent(0.01) else "보정 의심 ❌",
    )
    assert r.is_consistent(alpha=0.01), "미당첨이 길어지면 확률이 변함"


@pytest.mark.parametrize(
    "prizes",
    [
        (Prize("1등", 0.5), Prize("2등", 0.4)),                      # 합 90%
        (Prize("1등", 0.5), Prize("1등", 0.5)),                      # 이름 중복
        (Prize("1등", 0.0), Prize("2등", 1.0)),                      # 0% 등급
    ],
)
def test_invalid_box_is_rejected(prizes):
    with pytest.raises(ValueError):
        LottoBox("잘못된 상자", prizes)


# VSCode 오른쪽 위 ▷(Run Python File) 버튼으로 이 파일을 직접 실행했을 때도
# pytest로 테스트를 돌려 로그를 보여준다. (C#의 Main 메서드 역할)
if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
