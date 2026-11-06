# gacha-probability-validator

게임사가 공시한 가챠 확률과 실제 뽑기 결과가 통계적으로 맞는지 검증합니다.

## 설치

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## 사용 예

```python
from gacha_validator import test_rate

r = test_rate(pulls=10_000, hits=72, advertised_rate=0.01)
print(r.observed_rate, r.p_value, (r.ci_low, r.ci_high))
print("공시 확률과 일치" if r.is_consistent() else "공시 확률과 불일치 (α=0.05)")
```

## 구조

```
src/gacha_validator/   패키지 코드 (stats.py: 이항검정)
tests/                 pytest 테스트
data/raw/              원본 뽑기 기록 (git 제외)
data/processed/        가공 데이터 (git 제외)
notebooks/             분석 노트북
```

## 테스트

```bash
pytest
```
