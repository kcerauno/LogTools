import io
import sys

import pytest

import re

from wk_logtool.coarsen import cli
from wk_logtool.coarsen.aggregator import (
    count_by_level,
    count_by_level_with_capture,
    extract_leading_timestamp,
)
from wk_logtool.coarsen.levels import get_level, make_daynight_level


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


def test_count_by_level_date_groups_by_year_month() -> None:
    lines = [
        "20091209 Wed 14:55:16\ta",
        "20091215 Tue 09:00:00\tb",
        "20160903 Sat 15:31:58\tc",
    ]
    result = count_by_level(lines, get_level("date"))
    formatted = [(dt.strftime(get_level("date").display_format), c) for dt, c in result]
    assert formatted == [("200912", 2), ("201609", 1)]


def test_count_by_level_skips_unparseable_and_missing_timestamps() -> None:
    lines = [
        "20260719 10:22:01\tok line",
        "\tno timestamp yet",
        "this line has no tab at all",
    ]
    result = count_by_level(lines, get_level("ms"))
    assert len(result) == 1
    assert result[0][1] == 1


def test_count_by_level_daynight_default_boundaries() -> None:
    lines = [
        "20091209 Wed 14:55:10\tafternoon",
        "20091209 Wed 22:55:10\tnight",
        "20091209 Wed 06:59:59\tstill previous night",
        "20091209 Wed 07:00:00\tjust day",
    ]
    level = get_level("daynight")
    result = count_by_level(lines, level)
    formatted = [(level.format(dt), count) for dt, count in result]
    assert formatted == [
        ("20091208 Tue night", 1),
        ("20091209 Wed day", 2),
        ("20091209 Wed night", 1),
    ]


def test_count_by_level_daynight_night_crosses_midnight_keeps_start_date() -> None:
    lines = ["20091210 Thu 01:55:10\tearly morning"]
    level = get_level("daynight")
    result = count_by_level(lines, level)
    formatted = [(level.format(dt), count) for dt, count in result]
    assert formatted == [("20091209 Wed night", 1)]


def test_make_daynight_level_custom_boundaries() -> None:
    level = make_daynight_level(day_start_hour=6, night_start_hour=20)
    lines = [
        "20091209 Wed 19:59:59\ta",
        "20091209 Wed 20:00:00\tb",
    ]
    result = count_by_level(lines, level)
    formatted = [(level.format(dt), count) for dt, count in result]
    assert formatted == [
        ("20091209 Wed day", 1),
        ("20091209 Wed night", 1),
    ]


def test_make_daynight_level_rejects_day_not_before_night() -> None:
    with pytest.raises(ValueError):
        make_daynight_level(day_start_hour=22, night_start_hour=7)


def test_cli_end_to_end_daynight_with_custom_boundaries(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    data = (
        b"20091209 Wed 14:55:16.000000\tfirst\n"
        b"20091209 Wed 21:55:16.000000\tsecond\n"
    )
    monkeypatch.setattr(sys, "stdin", _FakeStdin(data))
    exit_code = cli.main(["--level", "daynight", "--night-start-hour", "21"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == "1\t20091209 Wed day\n1\t20091209 Wed night\n"


def test_cli_daynight_invalid_boundaries_shows_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    data = b"20091209 Wed 14:55:16.000000\tfirst\n"
    monkeypatch.setattr(sys, "stdin", _FakeStdin(data))
    exit_code = cli.main(
        ["--level", "daynight", "--day-start-hour", "22", "--night-start-hour", "7"]
    )
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "エラー" in captured.err


def test_count_by_level_with_capture_groups_by_bucket_and_captured_value() -> None:
    lines = [
        "20091209 Wed 14:55:10\tMESSAGES: ERR-600 something",
        "20091209 Wed 22:55:10\tMESSAGES: ERR-4030 oops",
        "20091209 Wed 22:58:10\tMESSAGES: ERR-4031 oops",
        "20091209 Wed 14:56:10\tMESSAGES: ERR-600 duplicate",
    ]
    daynight = get_level("daynight")
    pattern = re.compile(r"MESSAGES: (ERR-\d+)")
    result = count_by_level_with_capture(lines, daynight, pattern)
    formatted = [(daynight.format(dt), captured, count) for dt, captured, count in result]
    assert formatted == [
        ("20091209 Wed day", "ERR-600", 2),
        ("20091209 Wed night", "ERR-4030", 1),
        ("20091209 Wed night", "ERR-4031", 1),
    ]


def test_count_by_level_with_capture_skips_non_matching_lines() -> None:
    lines = [
        "20091209 Wed 14:55:10\tno error code here",
        "20091209 Wed 14:56:10\tMESSAGES: ERR-600 matched",
    ]
    pattern = re.compile(r"MESSAGES: (ERR-\d+)")
    result = count_by_level_with_capture(lines, get_level("date"), pattern)
    assert len(result) == 1
    assert result[0][1] == "ERR-600"
    assert result[0][2] == 1


def test_cli_end_to_end_with_capture_regex(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    data = (
        b"20091209 Wed 14:55:10\tMESSAGES: ERR-600 something\n"
        b"20091209 Wed 22:55:10\tMESSAGES: ERR-4030 oops\n"
        b"20091209 Wed 22:58:10\tMESSAGES: ERR-4031 oops\n"
    )
    monkeypatch.setattr(sys, "stdin", _FakeStdin(data))
    exit_code = cli.main(
        ["--level", "daynight", "--capture-regex", r"MESSAGES: (ERR-\d+)"]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == (
        "1\t20091209 Wed day ERR-600\n"
        "1\t20091209 Wed night ERR-4030\n"
        "1\t20091209 Wed night ERR-4031\n"
    )


def test_cli_capture_regex_without_group_shows_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    data = b"20091209 Wed 14:55:10\tMESSAGES: ERR-600 something\n"
    monkeypatch.setattr(sys, "stdin", _FakeStdin(data))
    exit_code = cli.main(
        ["--level", "date", "--capture-regex", r"MESSAGES: ERR-\d+"]
    )
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "エラー" in captured.err


def test_cli_capture_regex_invalid_pattern_shows_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    data = b"20091209 Wed 14:55:10\tMESSAGES: ERR-600 something\n"
    monkeypatch.setattr(sys, "stdin", _FakeStdin(data))
    exit_code = cli.main(["--level", "date", "--capture-regex", r"(unclosed"])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "エラー" in captured.err


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
