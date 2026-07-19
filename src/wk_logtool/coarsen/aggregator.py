"""行頭タイムスタンプの抽出と、丸めレベルごとの件数集計。"""

from __future__ import annotations

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


def count_by_level(lines: Iterable[str], level: Level) -> list[tuple[datetime, int]]:
    """各行の先頭タイムスタンプを指定レベルで丸め、件数を集計する。

    パースできない/存在しない行は集計対象から除外する。
    戻り値は丸めた日時の昇順にソート済み。
    """
    counts: Counter[datetime] = Counter()
    for line in lines:
        head = extract_leading_timestamp(line)
        if head is None:
            continue
        try:
            dt = dateutil_parser.parse(head)
        except (ValueError, OverflowError, TypeError):
            continue
        counts[level.truncate(dt)] += 1
    return sorted(counts.items())
