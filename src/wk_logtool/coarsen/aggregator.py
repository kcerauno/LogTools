"""行頭タイムスタンプの抽出と、丸めレベルごとの件数集計。"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from datetime import datetime

from dateutil import parser as dateutil_parser

from .levels import Level


def extract_leading_timestamp(line: str) -> str | None:
    """行頭からタブ文字までの部分を取り出す。

    retimeの出力(``<タイムスタンプ>\\tログ原文``)を想定している。
    タブがない行、またはタブより前が空の行(タイムスタンプ未確定行)は
    Noneを返す。
    """
    head, sep, _rest = line.partition("\t")
    if not sep or not head:
        return None
    return head


def _iter_timestamps(lines: Iterable[str]) -> Iterable[tuple[str, datetime]]:
    """各行から先頭タイムスタンプをパースする。

    タブがない/タイムスタンプ未確定/パース失敗の行は除外し、
    (行全体, パース済み日時) のペアを返す。
    """
    for line in lines:
        head = extract_leading_timestamp(line)
        if head is None:
            continue
        try:
            dt = dateutil_parser.parse(head)
        except (ValueError, OverflowError, TypeError):
            continue
        yield line, dt


def count_by_level(lines: Iterable[str], level: Level) -> list[tuple[datetime, int]]:
    """各行の先頭タイムスタンプを指定レベルで丸め、件数を集計する。

    パースできない/存在しない行は集計対象から除外する。
    戻り値は丸めた日時の昇順にソート済み。
    """
    counts: Counter[datetime] = Counter()
    for _line, dt in _iter_timestamps(lines):
        counts[level.truncate(dt)] += 1
    return sorted(counts.items())


def count_by_level_with_capture(
    lines: Iterable[str],
    level: Level,
    capture_pattern: re.Pattern[str],
) -> list[tuple[datetime, str, int]]:
    """丸めたタイムスタンプに、正規表現の最初のキャプチャグループで
    マッチした文字列を連結したキーでグルーピングし、件数を集計する。

    ``capture_pattern`` は行全体(タイムスタンプ含む)に対して検索する。
    マッチしない行、キャプチャグループ1が値を持たない行(未参加の
    グループなど)は集計対象から除外する。
    戻り値は (丸めた日時, キャプチャ文字列) の昇順にソート済み。
    """
    counts: Counter[tuple[datetime, str]] = Counter()
    for line, dt in _iter_timestamps(lines):
        match = capture_pattern.search(line)
        if match is None:
            continue
        captured = match.group(1)
        if captured is None:
            continue
        counts[(level.truncate(dt), captured)] += 1
    return [
        (bucket_dt, captured, count)
        for (bucket_dt, captured), count in sorted(counts.items())
    ]
