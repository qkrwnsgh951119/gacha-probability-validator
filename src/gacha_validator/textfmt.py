"""터미널 출력용 문자열 도구. 한글처럼 화면에서 2칸을 차지하는 글자를 고려해 정렬한다."""

import unicodedata
from collections.abc import Sequence


def display_width(text: str) -> int:
    """화면에 표시되는 폭. 한글·전각 문자·이모지(✅ 등)는 2칸으로 센다."""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def pad(text: str, width: int, align: str = "<") -> str:
    """화면 폭 기준으로 width칸에 맞춰 공백을 채운다. align: "<" 왼쪽, ">" 오른쪽."""
    fill = " " * max(width - display_width(text), 0)
    return fill + text if align == ">" else text + fill


def format_table(
    headers: Sequence[str],
    rows: Sequence[Sequence[object]],
    align: str | None = None,
    gap: int = 3,
) -> list[str]:
    """헤더와 행을 받아 열이 맞춰진 줄 목록을 돌려준다.

    align은 열마다 "<"(왼쪽) 또는 ">"(오른쪽)를 적은 문자열. 생략하면 첫 열만 왼쪽 정렬.
    """
    cells = [[str(c) for c in headers]] + [[str(c) for c in row] for row in rows]
    ncol = len(headers)
    if align is None:
        align = "<" + ">" * (ncol - 1)
    widths = [max(display_width(r[i]) for r in cells) for i in range(ncol)]
    sep = " " * gap
    lines = []
    for r in cells:
        lines.append(sep.join(pad(r[i], widths[i], align[i]) for i in range(ncol)).rstrip())
    return lines


def fmt_pct(rate: float) -> str:
    """확률을 %로. 보통은 소수 둘째 자리, 아주 작은 값은 0이 아닌 자리까지 보여 준다.

    0.01 → "1.00%", 0.000000001 → "0.0000001%", 0.989000001 → "98.9000001%"
    """
    if rate == 0:
        return "0%"
    s = f"{rate * 100:.10f}".rstrip("0")
    whole, _, frac = s.partition(".")
    frac = frac.ljust(2, "0")
    return f"{whole}.{frac}%"
