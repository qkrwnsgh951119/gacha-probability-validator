import functools
import math
import random
import sys

import pytest

from gacha_validator import test_rate as rate_test
from gacha_validator.lotto import LottoBox, Prize, simulate
from gacha_validator.lotto_buggy import make_buggy
from gacha_validator.textfmt import fmt_pct

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

# ── 실행 설정: 여기 두 값만 바꿔서 돌리면 됩니다 ──
MODE = "normal"  # "normal": 정상 상자 / "bug": 버그 버전 상자 (lotto_buggy.py)
OPENS = 10_000  # 개봉 횟수: 1_000(천) / 10_000(만) / 100_000(십만) 등
# 명령줄에서는 파일을 고치지 않고 덮어쓸 수 있습니다:
#   pytest tests/test_lotto.py --mode bug --opens 100000
#   pytest tests/test_lotto.py -v        ← 개별 개봉·누적 집계까지 보기

MODE_TEXT = {
    "normal": "정상 (normal): 설정 확률대로 만든 상자",
    "bug": "버그 (bug): 버그를 넣은 상자 (lotto_buggy.py)",
}


def resolve_settings(config) -> tuple[str, int]:
    """파일 설정(MODE, OPENS)과 명령줄 옵션(--mode, --opens)을 합쳐 실제 실행 값을 정한다."""
    mode = config.getoption("--mode") or MODE
    if mode not in MODE_TEXT:
        raise ValueError(f'MODE는 "normal" 또는 "bug"여야 합니다: {mode!r}')
    raw = config.getoption("--opens")
    n = OPENS if raw is None else int(str(raw).replace(",", ""))
    if n <= 0:
        raise ValueError(f"개봉 횟수는 1 이상이어야 합니다: {n}")
    return mode, n


def report_header(config) -> list[tuple[str, str]]:
    """보고서 맨 위에 붙일 항목. (conftest.py가 호출)"""
    try:
        mode, n = resolve_settings(config)
    except ValueError as e:
        return [("실행 모드", f"⚠ 설정 오류: {e}")]
    return [
        ("검증 대상", f"{LOTTO_TEST.name} 상자 ("
         + ", ".join(f"{p.name} {fmt_pct(p.rate)}" for p in LOTTO_TEST.prizes) + ")"),
        ("실행 모드", MODE_TEXT[mode]),
        ("개봉 횟수", f"{n:,}회"),
    ]


@pytest.fixture
def box(request):
    """MODE 설정에 따라 정상 상자 또는 버그 버전 상자를 돌려준다."""
    mode, _ = resolve_settings(request.config)
    return LOTTO_TEST if mode == "normal" else make_buggy(LOTTO_TEST)


@pytest.fixture
def opens(request):
    """OPENS 설정(또는 --opens)에 따른 개봉 횟수."""
    return resolve_settings(request.config)[1]


# ───────────────────── 설명 문장 도우미 ─────────────────────


def eun(word: str) -> str:
    """받침에 맞춰 '은/는'을 붙인다. (1등 → 1등은, 2번 → 2번은, 아이템 → 아이템은)"""
    last = word[-1]
    if "가" <= last <= "힣":
        return word + ("은" if (ord(last) - 0xAC00) % 28 else "는")
    return word + "은"


def how_rare(p_value: float) -> str:
    """p-value를 'N번에 1번' 같은 말로 바꾼다."""
    if p_value < 1e-6:
        return "100만 번에 1번도 안 될 만큼 드문 일"
    return f"약 {round(1 / p_value):,}번에 1번 있을 만큼 드문 일"


def fmt_p(p_value: float) -> str:
    return "0.0001 미만" if p_value < 0.0001 else f"{p_value:.4f}"


def opens_needed(rate: float, alpha: float) -> int:
    """이 등급이 '한 번도 안 나오는' 버그를 잡으려면 필요한 대략적인 개봉 횟수."""
    n = math.log(alpha) / math.log(1 - rate)
    return int(-(-n // 1000) * 1000)  # 천 단위 올림


# ───────────────────────── 상자 검증 ─────────────────────────


@pytest.mark.tc("확률표 합계 확인", "실제 뽑기에 쓰는 확률표의 합계가 100%인지",
                group="상자 검증", no=1)
def test_rate_table_sums_to_100(box, tc):
    """실제 뽑기에 쓰는 확률표의 합계가 100%인지 확인한다."""
    actual = getattr(box, "actual_rates", None) or tuple(p.rate for p in box.prizes)
    total = sum(actual)
    ok = abs(total - 1) <= 1e-9

    rows = [
        (p.name, fmt_pct(p.rate), fmt_pct(r), f"{r / total:.2%}" if total else "-")
        for p, r in zip(box.prizes, actual)
    ]
    rows.append(("합계", fmt_pct(sum(p.rate for p in box.prizes)), fmt_pct(total), "100.00%"))
    tc.table(("등급", "공시 확률", "실제 설정값", "실제로 나오는 확률"), rows, align="<>>>")

    changed = [p.name for p, r in zip(box.prizes, actual) if abs(p.rate - r) > 1e-12]
    if ok:
        tc.explain("확률표 합계가 정확히 100%입니다." if not changed else
                   "확률표 합계는 100%입니다.")
    else:
        short = (1 - total) * 100
        word = "모자랍니다" if short > 0 else "넘칩니다"
        tc.explain(f"실제 확률표 합계가 {fmt_pct(total)}로, 100%보다 {f"{abs(short):.7f}".rstrip("0").rstrip(".")}%p {word}.")
        # 합계가 100%가 아니면 나머지가 비율대로 나눠 붙어, 설정값을 안 바꾼 등급의 확률도 바뀐다
        untouched = [(p, r / total) for p, r in zip(box.prizes, actual)
                     if r > 0 and p.name not in changed]
        if untouched:
            p, eff = max(untouched, key=lambda x: abs(x[1] - x[0].rate))
            tc.explain(f"그 차이가 다른 등급에 비율대로 나눠 붙어서, 설정값을 안 바꾼 {eun(p.name)} "
                       f"{fmt_pct(p.rate)}가 아니라 {eff:.2%}로 나오게 됩니다.")
    if changed:
        tc.explain(f"또 {eun(', '.join(changed))} 실제 설정값이 공시 확률과 다릅니다.")

    assert ok, f"확률표 합계가 100%가 아닙니다: {total:.7%}"


@pytest.mark.tc("등급별 확률 검증", "상자를 여러 번 열어 등급별로 설정 확률대로 나오는지 비교",
                group="상자 검증", no=2)
def test_lotto_box_matches_configured_rates(box, opens, detail, tc):
    """상자를 OPENS번 열어 등급별 결과가 설정(공시) 확률대로 나오는지 검증한다.

    실행할 때마다 결과가 달라진다. 정상 상자라도 약 1% 확률로 우연히 불일치가
    나올 수 있으며, 그때는 보고서의 seed로 같은 결과를 재현할 수 있다.
    """
    tc.check = f"{box.name} 상자를 {opens:,}번 열어 등급별로 설정 확률대로 나오는지 비교"
    result = simulate(box, opens=opens, progress_every=max(opens // 10, 1),
                      verbose=detail, report=False)
    a = result.per_prize_alpha
    tc.shared["per_prize_alpha"] = a

    rows = []
    for s in result.stats:
        t = s.test
        diff = (t.observed_rate - s.prize.rate) * 100
        rows.append((
            s.prize.name, fmt_pct(s.prize.rate), f"{s.expected_hits:,.1f}", f"{t.hits:,}",
            f"{t.observed_rate:.2%}", f"{diff:+.2f}%p", fmt_p(t.p_value),
            "✅" if t.is_consistent(a) else "❌",
        ))
    tc.table(("등급", "설정 확률", "기대 횟수", "실제 횟수", "실제 확률", "차이", "p-value", "판정"),
             rows, align="<>>>>>><")
    tc.line(f"(seed={result.seed}: 같은 결과를 다시 보려면 simulate(..., seed={result.seed}))")

    bad = [s for s in result.stats if not s.test.is_consistent(a)]
    if not bad:
        tc.explain("모든 등급이 설정 확률과 같은 수준으로 나왔습니다. "
                   "설정값과의 차이는 우연히 생길 수 있는 범위 안이에요.")
    else:
        tc.explain(f"{len(bad)}개 등급이 설정 확률과 다르게 나왔습니다.")
        for s in bad:
            t = s.test
            gap = t.hits - s.expected_hits
            more = f"{abs(gap):,.0f}번 {'더' if gap > 0 else '덜'} 나옴"
            never = ", 한 번도 안 나옴" if t.hits == 0 else ""
            tc.explain(
                f"- {s.prize.name}: {fmt_pct(s.prize.rate)}로 설정했는데 실제로는 {t.observed_rate:.2%} "
                f"(기대 {s.expected_hits:,.0f}번 → 실제 {t.hits:,}번, {more}{never})",
                f"  우연히 이 정도 차이가 날 확률은 {how_rare(t.p_value)}입니다.",
            )
        if box is LOTTO_TEST:
            tc.explain("※ 정상 상자도 드물게(약 100번에 1번) 우연히 실패할 수 있어요. "
                       "다시 돌려도 같은 등급이 계속 실패하면 실제 문제입니다.")

    # 기대 횟수가 너무 적어 검증력이 약한 등급 안내 (통과했더라도)
    for s in result.stats:
        if s.expected_hits < 5 and s.test.is_consistent(a):
            tc.explain(
                f"참고: {eun(s.prize.name)} {opens:,}번에 평균 {s.expected_hits:.1f}번만 나오는 등급이라 "
                f"{s.test.hits}번이어도 이상하다고 보기 어려워요. 이 등급까지 확실히 보려면 "
                f"{opens_needed(s.prize.rate, a):,}번 이상 돌려 보세요."
            )

    assert sum(s.test.hits for s in result.stats) == opens
    assert result.is_consistent(), f"설정 확률과 불일치 (seed={result.seed})"


@pytest.mark.tc("결과 재현성", "같은 seed(난수 시작값)로 두 번 돌리면 결과가 똑같은지",
                group="상자 검증", no=3)
def test_same_seed_gives_same_result(box, opens, tc):
    """같은 seed로 두 번 돌리면 결과가 똑같아야 한다."""
    a = simulate(box, opens=opens, seed=42, verbose=False)
    b = simulate(box, opens=opens, seed=42, verbose=False)
    ha, hb = [s.test.hits for s in a.stats], [s.test.hits for s in b.stats]
    names = [s.prize.name for s in a.stats]
    tc.table(("실행", *names), [("1회차", *(f"{h:,}" for h in ha)), ("2회차", *(f"{h:,}" for h in hb))])
    tc.explain("두 번 모두 결과가 같아서, 문제가 생기면 seed로 똑같이 다시 재현할 수 있어요."
               if ha == hb else "같은 seed인데 결과가 달라서, 문제가 생겨도 다시 재현할 수 없어요.")
    assert ha == hb


# ──────────────── 도구 점검 (모드와 무관, 항상 정상 상자 기준) ────────────────


@pytest.mark.tc("조작 상자 탐지", "1등이 실제로는 0.3%인 조작 상자를 공지 1% 기준으로 검사하면 잡아내는지",
                no=4)
def test_rigged_box_is_detected(tc):
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
    caught = not check.is_consistent(alpha=0.01)
    tc.line(f"{opens:,}번 중 1등 {first_hits}번 ({check.observed_rate:.2%}), "
            f"공지 1%대로면 약 {opens * 0.01:,.0f}번 나와야 함 · p-value {fmt_p(check.p_value)}")
    tc.explain("공지보다 1등이 훨씬 적게 나오는 상자를 검증 도구가 '불일치'로 정확히 잡아냈어요."
               if caught else "조작된 상자인데 검증 도구가 잡아내지 못했어요.")
    assert caught


@functools.cache
def independence_sample() -> tuple[str, ...]:
    """TC-5, TC-6이 함께 쓰는 개봉 결과. 정상 상자를 20만 번 연다. (seed 고정: 매번 같은 결과)"""
    rng = random.Random(2026)
    return tuple(LOTTO_TEST.open(rng).name for _ in range(200_000))


def condition_table(tc, checks) -> list:
    """(상황, 다음 결과, 당첨, 시도, 설정 확률, 검정 결과) 목록을 표로 그리고, 어긋난 것만 돌려준다."""
    tc.table(
        ("상황", "다음 결과", "횟수", "실제 확률", "설정 확률", "판정"),
        [(s, n, f"{h:,}/{t:,}", f"{rr.observed_rate:.2%}", fmt_pct(p),
          "✅" if rr.is_consistent(0.01) else "❌") for s, n, h, t, p, rr in checks],
        align="<<>>><",
    )
    return [c for c in checks if not c[5].is_consistent(0.01)]


@pytest.mark.tc("독립시행 확인", "직전에 나온 결과가 다음 결과의 확률에 영향을 주지 않는지 (20만 번)", no=5)
def test_each_open_is_independent(tc):
    """직전에 X가 나왔어도 다음에 X가 나올 확률은 그대로여야 한다. (연속 당첨 보정 없음)"""
    results = independence_sample()
    pairs = list(zip(results, results[1:]))  # (직전 결과, 다음 결과)

    checks = []
    for prize in LOTTO_TEST.prizes:
        after_same = [nxt for prev, nxt in pairs if prev == prize.name]
        hits = sum(nxt == prize.name for nxt in after_same)
        r = rate_test(pulls=len(after_same), hits=hits, advertised_rate=prize.rate)
        checks.append((f"직전에 {prize.name}", f"또 {prize.name}", hits, len(after_same), prize.rate, r))

    bad = condition_table(tc, checks)
    if not bad:
        tc.explain("직전에 무엇이 나왔든 다음 뽑기는 매번 같은 확률로 뽑힙니다.")
    for s, n, _, _, p, rr in bad:
        tc.explain(f"- '{s}' 다음에 '{n}' 확률이 {rr.observed_rate:.2%}로 설정 {fmt_pct(p)}와 달라요. "
                   "이전 결과가 다음 뽑기에 영향을 주고 있을 수 있습니다.")
    assert not bad


STREAK = 100  # 이만큼 연속으로 1등이 안 나온 뒤를 본다


@pytest.mark.tc("연속 미당첨 후 보정 없음 확인",
                f"1등이 {STREAK}번 넘게 연속으로 안 나온 뒤에도 1등 확률이 그대로 1%인지 (20만 번)", no=6)
def test_no_pity_after_losing_streak(tc):
    """1등이 STREAK번 넘게 안 나왔어도 다음 1등 확률은 그대로 1%여야 한다. (천장/보정 없음)"""
    first = LOTTO_TEST.prizes[0]
    streak, trials, hits = 0, 0, 0
    for name in independence_sample():
        if streak >= STREAK:
            trials += 1
            hits += name == first.name
        streak = 0 if name == first.name else streak + 1
    r = rate_test(pulls=trials, hits=hits, advertised_rate=first.rate)

    bad = condition_table(tc, [(f"{first.name} {STREAK}연속 꽝 뒤", first.name, hits, trials, first.rate, r)])
    if not bad:
        tc.explain(f"오래 안 나와도 {first.name} 확률이 올라가지 않습니다. (천장·보정 없음)")
    else:
        direction = "올라갑니다" if r.observed_rate > first.rate else "내려갑니다"
        tc.explain(f"{STREAK}번 연속 꽝 뒤에는 {first.name} 확률이 {r.observed_rate:.2%}로, "
                   f"설정 {fmt_pct(first.rate)}보다 {direction}. 숨은 천장이나 보정이 있을 수 있습니다.")
    assert not bad


INVALID_BOXES = [
    pytest.param((Prize("1등", 0.5), Prize("2등", 0.4)), "확률 합계가 90%인", id="합계90%"),
    pytest.param((Prize("1등", 0.5), Prize("1등", 0.5)), "등급 이름이 중복된", id="이름중복"),
    pytest.param((Prize("1등", 0.0), Prize("2등", 1.0)), "확률이 0%인 등급이 있는", id="0%등급"),
]


@pytest.mark.tc("잘못된 확률표 거부", "잘못된 확률표를 넣으면 오류로 막는지", no=7)  # 경우 3개: TC-7~9
@pytest.mark.parametrize("prizes,problem", INVALID_BOXES)
def test_invalid_box_is_rejected(prizes, problem, tc):
    tc.check = f"{problem} 확률표를 넣으면 오류로 막는지"
    with pytest.raises(ValueError) as e:
        LottoBox("잘못된 상자", prizes)
    tc.explain(f"잘못된 설정을 미리 막아 줍니다. (안내 문구: {e.value})")


# VSCode 오른쪽 위 ▷(Run Python File) 버튼으로 이 파일을 직접 실행했을 때도
# pytest로 테스트를 돌려 보고서를 보여준다. (C#의 Main 메서드 역할)
if __name__ == "__main__":
    # 예) python tests/test_lotto.py --mode bug --opens 10000 -v
    raise SystemExit(pytest.main([__file__, *sys.argv[1:]]))
