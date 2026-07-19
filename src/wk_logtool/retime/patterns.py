"""既知の日時フォーマット候補(正規表現)一覧。

ログファイルごと・行ごとにフォーマットが異なりうるという前提のもと、
「ファイル全体で1フォーマットに決め打ちする」のではなく、行ごとに
この候補群すべてに対して総当りでマッチを試みる。

各パターンは名前付きグループ ``ts`` でタイムスタンプ部分文字列を
キャプチャする。実際の日時への変換は dateutil.parser に委譲するため、
ここでは「タイムスタンプらしい部分文字列を過不足なく切り出す」ことだけに
専念する(strptimeフォーマット文字列は持たない)。

新しいログ形式に対応する場合は、このリストに要素を追加するだけでよい。
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field


def _identity(s: str) -> str:
    return s


@dataclass(frozen=True)
class PatternSpec:
    name: str
    regex: re.Pattern[str]
    #: 切り出した文字列を dateutil.parser.parse に渡す前に正規化する関数。
    #: dateutil がそのままでは解釈できない書式(例: Apache combined log
    #: formatの "dd/Mon/yyyy:HH:MM:SS" のような日付と時刻の区切りが
    #: コロンになっている形式)を吸収するために使う。
    normalize: Callable[[str], str] = field(default=_identity)


def _p(
    name: str, pattern: str, normalize: Callable[[str], str] = _identity
) -> PatternSpec:
    return PatternSpec(name=name, regex=re.compile(pattern), normalize=normalize)


def _normalize_apache_clf(s: str) -> str:
    # "19/Jul/2026:10:22:05 +0900" -> "19/Jul/2026 10:22:05 +0900"
    # 日付と時刻を区切る最初のコロンだけを空白に置き換える。
    return s.replace(":", " ", 1)


# 優先順位は「同じ開始位置・同じ長さのマッチが複数候補で競合した場合」の
# タイブレークにのみ使う(通常は開始位置が最も早いマッチが優先される)。
CANDIDATE_PATTERNS: list[PatternSpec] = [
    # 2026-07-19T10:22:01.123456+09:00 / 2026-07-19 10:22:01Z など (ISO8601)
    _p(
        "iso8601",
        r"(?P<ts>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?"
        r"(?:Z|[+-]\d{2}:?\d{2})?)",
    ),
    # 19/Jul/2026:10:22:01 +0900 (Apache/nginx combined log format)
    _p(
        "apache_clf",
        r"(?P<ts>\d{2}/[A-Za-z]{3}/\d{4}:\d{2}:\d{2}:\d{2}\s[+-]\d{4})",
        normalize=_normalize_apache_clf,
    ),
    # 2026/07/19 10:22:01.123
    _p(
        "slash_date",
        r"(?P<ts>\d{4}/\d{1,2}/\d{1,2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?)",
    ),
    # 2026.07.19 10:22:01
    _p(
        "dot_date",
        r"(?P<ts>\d{4}\.\d{1,2}\.\d{1,2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?)",
    ),
    # 20260719 10:22:01.123456 (セパレータなし日付)
    _p(
        "compact_date",
        r"(?P<ts>\d{8}[ T]\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?)",
    ),
    # 07/19/2026 10:22:01 (米国式)
    _p(
        "us_date",
        r"(?P<ts>\d{1,2}/\d{1,2}/\d{4}[ T]\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?)",
    ),
    # Jul 19 10:22:01 (BSD syslog形式、年なし)
    _p(
        "syslog_bsd",
        r"(?P<ts>\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"\s+\d{1,2}\s\d{2}:\d{2}:\d{2}\b)",
    ),
    # Sat Sep 03 15:31:58 2016 (Oracle Database Alert LogのUnix ctime形式)
    # 1桁日を "Sep  3" のようにスペース埋めする書式にも対応。
    _p(
        "oracle_alert_ctime",
        r"(?P<ts>\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+\d{4}\b)",
    ),
]
