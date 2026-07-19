import io
import sys

import pytest

from wk_logtool.coarsen import cli
from wk_logtool.coarsen.aggregator import count_by_level, extract_leading_timestamp
from wk_logtool.coarsen.levels import get_level


def test_extract_leading_timestamp_basic() -> None:
    assert extract_leading_timestamp("20260719 10:22:01\tsomething happened") == (
        "20260719 10:22:01"
    )


def test_extract_leading_timestamp_no_tab_returns_none() -> None:
    assert extract_leading_timestamp("no tab in this line") is None


def test_extract_leading_timestamp_empty_head_returns_none() -> None:
    assert extract_leading_timestamp("\tcontinuation line, no timestamp yet") is None


def test_count_by_level_ms_keeps_full_precision() -> None:
    lines = [
        "20091209 Wed 14:55:16.000000\tfirst",
        "20091209 Wed 14:55:16.000000\tsecond",
        "20160903 Sat 15:31:58.000000\tthird",
    ]
    result = count_by_level(lines, get_level("ms"))
    formatted = [(dt.strftime("%Y%m%d %a %H:%M:%S"), count) for dt, count in result]
    assert formatted == [
        ("20091209 Wed 14:55:16", 2),
        ("20160903 Sat 15:31:58", 1),
    ]


def test_count_by_level_sec1_floors_to_ten_seconds() -> None:
    lines = [
        "20260719 Sun 10:22:01\ta",
        "20260719 Sun 10:22:05\tb",
        "20260719 Sun 10:22:19\tc",
    ]
    result = count_by_level(lines, get_level("sec1"))
    formatted = [(dt.strftime("%Y%m%d %a %H:%M:%S"), count) for dt, count in result]
    assert formatted == [
        ("20260719 Sun 10:22:00", 2),
        ("20260719 Sun 10:22:10", 1),
    ]


def test_count_by_level_date_collapses_everything() -> None:
    lines = [
        "20091209 Wed 14:55:16\ta",
        "20160903 Sat 15:31:58\tb",
        "20160903 Sat 15:32:27\tc",
    ]
    result = count_by_level(lines, get_level("date"))
    assert len(result) == 1
    dt, count = result[0]
    assert count == 3
    assert dt.strftime(get_level("date").display_format) == ""


def test_count_by_level_skips_unparseable_and_missing_timestamps() -> None:
    lines = [
        "20260719 10:22:01\tok line",
        "\tno timestamp yet",
        "this line has no tab at all",
    ]
    result = count_by_level(lines, get_level("ms"))
    assert len(result) == 1
    assert result[0][1] == 1


def test_no_files_and_no_piped_stdin_shows_error_and_usage(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    exit_code = cli.main(["--level", "hour"])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "usage:" in captured.err
    assert "エラー" in captured.err


class _FakeStdin:
    def __init__(self, data: bytes) -> None:
        self.buffer = io.BytesIO(data)

    def isatty(self) -> bool:
        return False


def test_cli_end_to_end_via_stdin(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    data = (
        b"20091209 Wed 14:55:16.000000\tfirst\n"
        b"20091209 Wed 14:55:16.000000\tsecond\n"
        b"20160903 Sat 15:31:58.000000\tthird\n"
    )
    monkeypatch.setattr(sys, "stdin", _FakeStdin(data))
    exit_code = cli.main(["--level", "weekday"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == "2\t20091209\n1\t20160903\n"
