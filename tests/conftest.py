"""pytest 공통 설정. 이 폴더의 모든 테스트 실행에 자동 적용된다.

pytest 기본 출력(점, 경로, 트레이스백 등)을 숨기고, 비전공자도 읽기 쉬운 보고서 형식으로 출력한다.

  맨 위   테스트 목적 · 실행 모드 · 개봉 횟수 · 실행 시각
  TC마다  [TC-번호] 검증 항목 / 확인 내용 / ✅·❌ 결과 / 쉬운 말 해석
  맨 아래 전체 TC 요약표 · 용어 설명

옵션
  -v, --verbose  개별 개봉 결과와 누적 집계도 출력
  --raw          이 보고서 대신 pytest 기본 출력을 그대로 사용 (개발자용, 트레이스백 확인)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime

import pytest

from gacha_validator.textfmt import display_width, format_table, pad

PURPOSE = "뽑기 상자가 설정(공시)한 확률대로 아이템을 내주는지 통계로 검증합니다."
LABEL_W = 11  # "확인 내용:" 등 라벨 칸 폭

ENABLED = pytest.StashKey[bool]()
DETAIL = pytest.StashKey[bool]()
RECORDS = pytest.StashKey[dict]()
SHARED = pytest.StashKey[dict]()
STARTED = pytest.StashKey[datetime]()


def pytest_addoption(parser):
    """명령줄에서 test_lotto.py의 MODE, OPENS 값을 덮어쓸 수 있게 한다.

    예) pytest tests/test_lotto.py --mode bug --opens 100000
    """
    parser.addoption("--mode", choices=["normal", "bug"], default=None,
                     help="normal: 정상 상자, bug: 버그 버전 상자")
    parser.addoption("--opens", default=None,
                     help="개봉 횟수 (예: 1000, 10000, 100_000)")
    parser.addoption("--raw", action="store_true",
                     help="읽기 쉬운 보고서 대신 pytest 기본 출력을 사용")


# ───────────────────────── TC 기록 ─────────────────────────


@dataclass
class TC:
    """테스트 하나의 보고 내용. 테스트 함수는 `tc` 픽스처로 받아 채운다."""

    no: int
    nodeid: str
    group: str
    name: str
    check: str
    lines: list[str] = field(default_factory=list)  # 결과 아래 보여 줄 숫자·표
    meaning: list[str] = field(default_factory=list)  # 쉬운 말 해석
    shared: dict = field(default_factory=dict)  # 보고서 전체가 함께 쓰는 값
    outcome: str = "passed"  # passed / failed / error / skipped
    error: str | None = None

    @property
    def label(self) -> str:
        return f"TC-{self.no}"

    def line(self, text: str = "") -> None:
        self.lines.append(text)

    def table(self, headers, rows, align=None) -> None:
        self.lines.extend(format_table(headers, rows, align))

    def explain(self, *texts: str) -> None:
        self.meaning.extend(texts)


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "tc(name, check, group, no): 보고서에 표시할 TC 이름·확인 내용·구분·번호"
    )
    config.stash[STARTED] = datetime.now()
    config.stash[ENABLED] = not config.getoption("--raw")
    # pytest 기본 출력은 최소화하고, 사용자가 준 -v는 '상세 로그 보기'로만 쓴다.
    config.stash[DETAIL] = config.option.verbose > 0
    config.stash[RECORDS] = {}
    config.stash[SHARED] = {}
    if config.stash[ENABLED]:
        config.option.verbose = -2  # 헤더·점(.)·통과 개수 줄 숨김
        config.option.no_summary = True  # 실패 트레이스백·경고 요약 숨김
        config.option.no_header = True
    if config.stash[DETAIL]:
        _attach_detail_log(config)


@pytest.fixture
def tc(request) -> TC:
    return request.config.stash[RECORDS][request.node.nodeid]


@pytest.fixture
def detail(request) -> bool:
    """-v(--verbose)로 실행했으면 True: 개별 개봉·누적 집계를 출력한다."""
    return request.config.stash[DETAIL]


def _sheet_no(item) -> int | None:
    """@pytest.mark.tc(..., no=N)로 정한 TC 번호 (테스트 시트 기준).

    여러 경우로 나눠 도는 테스트는 no가 첫 경우 번호이고, 다음 경우부터 1씩 늘어난다.
    (예: no=7이면 경우 3개가 TC-7, TC-8, TC-9)
    """
    marker = item.get_closest_marker("tc")
    if marker is None or "no" not in marker.kwargs:
        return None
    no = marker.kwargs["no"]
    callspec = getattr(item, "callspec", None)
    if callspec is not None and callspec.indices:
        no += next(iter(callspec.indices.values()))
    return no


def _make_record(no: int, item, shared: dict) -> TC:
    marker = item.get_closest_marker("tc")
    if marker:
        name, check = marker.args[:2]
        group = marker.kwargs.get("group", "도구 점검")
    else:  # 표시 정보가 없는 테스트는 함수 이름과 docstring 첫 줄을 쓴다
        name = item.name
        doc = (getattr(item.function, "__doc__", None) or "").strip()
        check = doc.splitlines()[0] if doc else "-"
        group = "기타"
    callspec = getattr(item, "callspec", None)
    if callspec is not None:  # 같은 테스트를 여러 경우로 돌리면 경우 이름을 붙여 구분
        # pytest는 한글 id를 \uXXXX로 바꿔 두므로 화면용으로 되돌린다
        case = callspec.id.encode("ascii", "backslashreplace").decode("unicode_escape")
        name = f"{name} ({case})"
    return TC(no, item.nodeid, group, name, check, shared=shared)


# ───────────────────────── 보고서 출력 ─────────────────────────


def _tr(config):
    return config.pluginmanager.get_plugin("terminalreporter")


def pytest_collection_finish(session):
    config = session.config
    records = config.stash[RECORDS]
    # 시트 번호가 있는 테스트는 그 번호로, 없는 테스트는 그 뒤에 이어서 번호를 매긴다.
    fixed = {item.nodeid: _sheet_no(item) for item in session.items}
    owner: dict[int, str] = {}
    for nodeid, no in fixed.items():
        if no is None:
            continue
        if no in owner:
            raise pytest.UsageError(f"TC-{no} 번호가 두 테스트에 겹칩니다: {owner[no]}, {nodeid}")
        owner[no] = nodeid
    next_no = max(owner, default=0) + 1
    for item in session.items:
        no = fixed[item.nodeid]
        if no is None:
            no, next_no = next_no, next_no + 1
        records[item.nodeid] = _make_record(no, item, config.stash[SHARED])
    if not config.stash[ENABLED] or _tr(config) is None:
        return

    # 테스트 모듈이 report_header(config)를 정의했으면 그 항목(실행 모드, 횟수 등)을 덧붙인다.
    extra, seen = [], set()
    for item in session.items:
        module = getattr(item, "module", None)
        if module is not None and module not in seen and hasattr(module, "report_header"):
            seen.add(module)
            extra.extend(module.report_header(config))

    started = config.stash[STARTED].strftime("%Y년 %m월 %d일 %H:%M:%S")
    rows = [("테스트 목적", PURPOSE), *extra, ("실행 시각", started),
            ("테스트 수", f"{len(session.items)}건")]
    if config.stash[DETAIL]:
        rows.append(("출력", "상세 (-v: 개별 개봉·누적 집계 포함)"))
    tr = _tr(config)
    tr.write_line("")
    tr.write_line("=" * 72, bold=True)
    tr.write_line("  가챠 확률 검증 테스트 보고서", bold=True)
    tr.write_line("=" * 72, bold=True)
    w = max(display_width(k) for k, _ in rows) + 2
    for k, v in rows:
        tr.write_line(f"  {pad(k, w)}{v}")
    tr.write_line("=" * 72, bold=True)


@pytest.hookimpl(wrapper=True)
def pytest_report_teststatus(report, config):
    """pytest가 테스트마다 찍는 점(.)·F 표시를 없앤다. (통과/실패 집계는 그대로)"""
    res = yield
    if config.stash[ENABLED] and isinstance(res, tuple) and len(res) == 3:
        return res[0], "", ""
    return res


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item, call):
    report = yield
    rec = item.config.stash[RECORDS].get(item.nodeid)
    if rec is None or report.passed:
        return report
    if report.skipped:
        rec.outcome = "skipped"
    elif call.excinfo is not None and call.excinfo.errisinstance(AssertionError) \
            and report.when == "call":
        rec.outcome = "failed"
    else:  # 검증 실패가 아니라 테스트 코드나 설정이 잘못돼 멈춘 경우
        rec.outcome = "error"
        exc = call.excinfo.value if call.excinfo else None
        rec.error = f"{type(exc).__name__}: {exc}" if exc else report.longreprtext[-300:]
    return report


def pytest_runtest_logstart(nodeid, location):
    _current["nodeid"] = nodeid
    _current["log_header_done"] = False


def pytest_runtest_logfinish(nodeid, location):
    _current["nodeid"] = None
    config = _current.get("config")
    if config is None or not config.stash[ENABLED]:
        return
    rec = config.stash[RECORDS].get(nodeid)
    if rec is not None:
        _write_tc(_tr(config), rec)


RESULT_TEXT = {
    "passed": "✅ 통과",
    "failed": "❌ 실패",
    "error": "❌ 실패 (테스트 실행 중 오류)",
    "skipped": "⏭ 건너뜀",
}


def _write_tc(tr, rec: TC) -> None:
    def labeled(label: str, texts: list[str], **markup) -> None:
        for i, text in enumerate(texts or [""]):
            head = pad(label + ":", LABEL_W) if i == 0 else " " * LABEL_W
            tr.write_line(f"  {head}{text}", **markup)

    tr.write_line("")
    tr.write_line(f"[{rec.label}] {rec.name}  ({rec.group})", bold=True)
    labeled("확인 내용", [rec.check])
    ok = rec.outcome == "passed"
    labeled("결과", [RESULT_TEXT[rec.outcome]], green=ok, red=rec.outcome in ("failed", "error"))
    for text in rec.lines:
        tr.write_line(" " * (2 + LABEL_W) + text if text else "")

    meaning = list(rec.meaning)
    if rec.outcome == "error":
        meaning = ["검증을 끝까지 하지 못했습니다. 상자 문제가 아니라 테스트 코드나 설정 문제일 수 있어요.",
                   f"오류 내용: {rec.error}",
                   "자세한 위치는 --raw 옵션으로 다시 실행하면 볼 수 있습니다."]
    elif not meaning:
        meaning = ["기대한 대로 동작합니다." if ok else "기대한 결과와 다릅니다."]
    labeled("해석", meaning)


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    if not config.stash[ENABLED]:
        return
    tr = terminalreporter
    records = sorted(config.stash[RECORDS].values(), key=lambda r: r.no)
    if not records:
        return

    tr.write_line("")
    tr.write_line("=" * 72, bold=True)
    tr.write_line("  전체 결과 요약", bold=True)
    tr.write_line("=" * 72, bold=True)
    rows = [(r.label, r.group, r.name, RESULT_TEXT[r.outcome].split(" (")[0]) for r in records]
    for line in format_table(("TC", "구분", "검증 항목", "결과"), rows, align="<<<<"):
        tr.write_line("  " + line)

    passed = sum(r.outcome == "passed" for r in records)
    bad = [r for r in records if r.outcome in ("failed", "error")]
    skipped = sum(r.outcome == "skipped" for r in records)
    tr.write_line("")
    counts = f"총 {len(records)}건 · 통과 {passed}건 · 실패 {len(bad)}건"
    if skipped:
        counts += f" · 건너뜀 {skipped}건"
    tr.write_line(f"  {counts}")

    errors = [r for r in bad if r.outcome == "error"]
    box_bad = [r for r in bad if r.outcome == "failed" and r.group == "상자 검증"]
    tool_bad = [r for r in bad if r.outcome == "failed" and r.group != "상자 검증"]
    if not bad:
        tr.write_line("  최종 판정: ✅ 모든 TC 통과. 상자가 설정 확률대로 동작합니다.", green=True, bold=True)
    if box_bad:
        ids = ", ".join(r.label for r in box_bad)
        tr.write_line(
            f"  최종 판정: ❌ 상자 검증 {len(box_bad)}건 실패 ({ids}). "
            "상자의 실제 동작이 설정과 다릅니다.", red=True, bold=True)
    if tool_bad:
        ids = ", ".join(r.label for r in tool_bad)
        tr.write_line(
            f"  ⚠ 도구 점검 {len(tool_bad)}건 실패 ({ids}). "
            "검증 도구 자체에 문제가 있을 수 있어 결과를 그대로 믿기 어렵습니다.", red=True, bold=True)
    if errors:
        ids = ", ".join(r.label for r in errors)
        tr.write_line(
            f"  ⚠ 실행 오류 {len(errors)}건 ({ids}). 검증을 끝까지 하지 못했습니다. "
            "설정값(MODE, OPENS 등)이나 테스트 코드를 확인하세요.", red=True, bold=True)

    alpha = config.stash[SHARED].get("per_prize_alpha")
    threshold = f"등급별 확률 검증은 {alpha:g}" if alpha else "보통 0.01"
    tr.write_line("")
    tr.write_line("  [용어 설명]")
    for line in (
        "  · p-value: 정상 상자라도 이만큼의 차이가 우연히 생길 확률. 판정 기준"
        f"({threshold})보다 작으면 '우연이라 보기 어렵다'고 보고 불일치로 판정합니다.",
        "  · 기대 횟수: 설정 확률대로라면 평균적으로 나와야 하는 횟수 (개봉 횟수 × 설정 확률).",
        "  · %p(퍼센트포인트): 확률끼리의 차이. 1.00%가 1.50%가 되면 0.50%p 차이입니다.",
    ):
        tr.write_line(line)


# ───────────────────────── -v 상세 로그 ─────────────────────────

_current: dict = {}


def pytest_sessionstart(session):
    _current["config"] = session.config


class _DetailHandler(logging.Handler):
    """테스트 실행 중 개봉 로그를 화면에 바로 쓴다. (pytest 출력 캡처를 잠시 끄고)"""

    def __init__(self, config):
        super().__init__(logging.INFO)
        self.config = config

    def emit(self, record):
        tr = _tr(self.config)
        capman = self.config.pluginmanager.get_plugin("capturemanager")
        if tr is None or capman is None:
            return
        with capman.global_and_fixture_disabled():
            if not _current.get("log_header_done"):
                _current["log_header_done"] = True
                rec = self.config.stash[RECORDS].get(_current.get("nodeid"))
                title = f"[{rec.label}] {rec.name}" if rec else ""
                tr.write_line("")
                tr.write_line(f"  ┄┄ {title} 상세 로그 (-v) ┄┄")
            tr.write_line("    " + self.format(record))


def _attach_detail_log(config):
    logger = logging.getLogger("gacha_validator")
    logger.setLevel(logging.INFO)
    logger.addHandler(_DetailHandler(config))
