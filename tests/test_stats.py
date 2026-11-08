import pytest

from gacha_validator import test_rate as rate_test


@pytest.mark.tc("이항검정: 정상 결과 통과", "1만 번 중 100번(1.00%) 당첨을 공시 1%와 비교하면 '일치'로 보는지", no=11)
def test_matching_rate_is_consistent(tc):
    r = rate_test(pulls=10_000, hits=100, advertised_rate=0.01)
    tc.line(f"p-value {r.p_value:.4f} · 95% 신뢰구간 {r.ci_low:.2%} ~ {r.ci_high:.2%}")
    tc.explain("공시 확률과 정확히 같은 결과를 '일치'로 판단했어요.")
    assert r.is_consistent()
    assert r.ci_low < 0.01 < r.ci_high


@pytest.mark.tc("이항검정: 이상 결과 탐지", "1만 번 중 40번(0.40%) 당첨을 공시 1%와 비교하면 '불일치'로 잡는지", no=12)
def test_far_too_few_hits_is_rejected(tc):
    r = rate_test(pulls=10_000, hits=40, advertised_rate=0.01)
    tc.line(f"p-value {r.p_value:.2e} (0.05보다 훨씬 작음)")
    tc.explain("공시(1%)보다 훨씬 적게 나온 결과를 '불일치'로 잡아냈어요.")
    assert not r.is_consistent()


@pytest.mark.tc("이항검정: 잘못된 입력 거부", "잘못된 숫자를 넣으면 오류로 막는지", no=13)  # 경우 3개: TC-13~15
@pytest.mark.parametrize("pulls,hits,rate,problem", [
    pytest.param(0, 0, 0.01, "뽑기 횟수가 0인", id="뽑기0번"),
    pytest.param(10, 11, 0.01, "당첨 수가 뽑기 횟수보다 많은", id="당첨초과"),
    pytest.param(10, 1, 0.0, "공시 확률이 0%인", id="확률0%"),
])
def test_invalid_input(pulls, hits, rate, problem, tc):
    tc.check = f"{problem} 입력을 넣으면 오류로 막는지"
    with pytest.raises(ValueError) as e:
        rate_test(pulls, hits, rate)
    tc.explain(f"잘못된 입력을 미리 막아 줍니다. (안내 문구: {e.value})")
