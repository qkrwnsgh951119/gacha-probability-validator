"""버그가 들어간 로또 상자. 검증 도구가 버그를 잡아내는지 확인하는 용도.

정상 상자(lotto.LottoBox)는 건드리지 않는다. 이 상자는 공시 확률표(prizes)는
정상 상자와 똑같이 보여 주지만, 실제 뽑기는 버그가 들어간 내부 확률표로 한다.

  버그① 1번 아이템: 1% → 0.0000001%
  버그② 4번 아이템: 0% (절대 안 나옴)
  버그③ 확률표 합계 검사 없음: 내부 확률표 합계가 100%가 아닌데(98.9000001%) 그대로 뽑는다.
        모자란 1.1%는 가중치 비율대로 나머지 아이템에 몰려,
        2번은 10% → 약 10.11%, 3번은 88.9% → 약 89.89%로 나온다.
"""

import random
from dataclasses import dataclass

from .lotto import LottoBox, Prize

BUG1_RATE = 0.000000001  # 0.0000001%
BUG2_RATE = 0.0


@dataclass(frozen=True)
class BuggyLottoBox:
    name: str
    prizes: tuple[Prize, ...]  # 공시(기획) 확률표: 검증 기준
    actual_rates: tuple[float, ...]  # 실제 뽑기에 쓰는 확률표 (버그 포함), prizes와 같은 순서

    @property
    def total_rate(self) -> float:
        """실제 뽑기에 쓰는 확률표의 합계."""
        return sum(self.actual_rates)

    def open(self, rng: random.Random) -> Prize:
        # 버그③: 합계가 100%인지 확인하지 않고 그대로 가중치로 쓴다.
        return rng.choices(self.prizes, weights=self.actual_rates)[0]


def make_buggy(box: LottoBox) -> BuggyLottoBox:
    """정상 상자를 받아, 같은 공시 확률표에 버그①②③이 들어간 상자를 만든다."""
    if len(box.prizes) < 4:
        raise ValueError("버그 버전은 아이템이 4개 이상인 상자에만 만들 수 있습니다.")
    rates = [p.rate for p in box.prizes]
    rates[0] = BUG1_RATE  # 버그① 1번 아이템 1% → 0.0000001%
    rates[3] = BUG2_RATE  # 버그② 4번 아이템 절대 안 나옴
    # 버그③: 위 두 값을 바꾼 뒤 합계를 다시 100%로 맞추지 않는다.
    return BuggyLottoBox(f"{box.name} [버그 버전]", box.prizes, tuple(rates))
