"""pytest 공통 설정. 이 폴더의 모든 테스트 실행에 자동 적용된다."""

from datetime import datetime

_started_at: datetime | None = None


def pytest_sessionstart(session):
    """테스트 실행 버튼을 누른 시각을 기록해 둔다."""
    global _started_at
    _started_at = datetime.now()


def pytest_unconfigure(config):
    """모든 출력이 끝난 뒤, 맨 마지막 줄에 실행 시각을 찍는다."""
    if _started_at is None:
        return
    reporter = config.pluginmanager.get_plugin("terminalreporter")
    if reporter is not None:
        started = _started_at.strftime("%Y년 %m월 %d일 %H:%M:%S")
        reporter.write_line(f"▶ 테스트 실행 시각: {started}", bold=True)
