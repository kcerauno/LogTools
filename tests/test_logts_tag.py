import io
import sys
from datetime import datetime

import pytest

from wk_logtool.common.text_encoding import decode_line
from wk_logtool.logts_tag import cli
from wk_logtool.logts_tag.tagger import LineTagger

DEFAULT = datetime(year=2026, month=1, day=1)
FMT = "%Y%m%d %H:%M:%S.%f"


def new_tagger(output_format: str = FMT, default: datetime = DEFAULT) -> LineTagger:
    return LineTagger(output_format=output_format, default_datetime=default)


def test_iso8601() -> None:
    tagger = new_tagger()
    out = tagger.tag_line("2026-07-19T10:22:01.123456+09:00 [INFO] started")
    assert out.startswith("20260719 10:22:01.123456\t")


def test_no_timestamp_line_carries_forward_previous() -> None:
    tagger = new_tagger()
    tagger.tag_line("2026-07-19T10:22:01 started")
    out = tagger.tag_line("  continuation line, no timestamp")
    assert out.startswith("20260719 10:22:01.000000\t")


def test_no_timestamp_before_any_seen_is_blank() -> None:
    tagger = new_tagger()
    out = tagger.tag_line("no timestamp at all")
    assert out.startswith("\t")


def test_apache_combined_log_format() -> None:
    tagger = new_tagger()
    out = tagger.tag_line("19/Jul/2026:10:22:05 +0900 GET /index.html 200")
    assert out.startswith("20260719 10:22:05.000000\t")


def test_syslog_missing_year_uses_default() -> None:
    tagger = new_tagger(default=datetime(year=2020, month=1, day=1))
    out = tagger.tag_line("Jan  5 03:00:00 host cron started")
    assert out.startswith("20200105 03:00:00.000000\t")


def test_multiple_timestamps_uses_earliest_occurring() -> None:
    tagger = new_tagger()
    out = tagger.tag_line("first=2026-01-01T00:00:00 second=2026-12-31T23:59:59")
    assert out.startswith("20260101 00:00:00.000000\t")


def test_output_format_is_configurable() -> None:
    tagger = new_tagger(output_format="%Y/%m/%d %H:%M:%S")
    out = tagger.tag_line("2026-07-19T10:22:01+09:00 hello")
    assert out.startswith("2026/07/19 10:22:01\t")


def test_decode_line_handles_utf8_shift_jis_and_euc_jp() -> None:
    utf8 = "こんにちは".encode("utf-8")
    sjis = "こんにちは".encode("shift_jis")
    eucjp = "こんにちは".encode("euc_jp")
    assert decode_line(utf8) == "こんにちは"
    assert decode_line(sjis) == "こんにちは"
    assert decode_line(eucjp) == "こんにちは"


def test_decode_line_empty_bytes() -> None:
    assert decode_line(b"") == ""


def test_no_files_and_no_piped_stdin_shows_error_and_usage(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    exit_code = cli.main([])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "usage:" in captured.err
    assert "エラー" in captured.err


class _FakeStdin:
    def __init__(self, data: bytes) -> None:
        self.buffer = io.BytesIO(data)

    def isatty(self) -> bool:
        return False


def test_no_files_with_piped_stdin_still_reads_stdin(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "stdin", _FakeStdin(b"2026-07-19T10:22:01 hello\n"))
    exit_code = cli.main([])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.startswith("20260719 10:22:01.000000\t")
