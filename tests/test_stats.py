import pytest

from gacha_validator import test_rate as rate_test


def test_matching_rate_is_consistent():
    r = rate_test(pulls=10_000, hits=100, advertised_rate=0.01)
    assert r.is_consistent()
    assert r.ci_low < 0.01 < r.ci_high


def test_far_too_few_hits_is_rejected():
    r = rate_test(pulls=10_000, hits=40, advertised_rate=0.01)
    assert not r.is_consistent()


@pytest.mark.parametrize("pulls,hits,rate", [(0, 0, 0.01), (10, 11, 0.01), (10, 1, 0.0)])
def test_invalid_input(pulls, hits, rate):
    with pytest.raises(ValueError):
        rate_test(pulls, hits, rate)
