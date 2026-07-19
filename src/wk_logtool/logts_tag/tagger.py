"""行ごとのタイムスタンプ抽出・変換・付与を行うコア処理。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from dateutil import parser as dateutil_parser

from .patterns import CANDIDATE_PATTERNS, PatternSpec


@dataclass(frozen=True)
class _RawMatch:
    start: int
    end: int
    text: str
    pattern_name: str
    normalize: Callable[[str], str]


def _find_earliest_match(
    line: str, patterns: list[PatternSpec]
) -> _RawMatch | None:
    """行内の全候補パターンを総当りし、最も先に出現するマッチを返す。

    同一行に複数のタイムスタンプがある場合は「先に出現したものを使う」
    という仕様のため、開始位置が最小のマッチを選ぶ。開始位置が同じ
    場合は、より長くマッチした(=より具体的な)候補を優先する。
    """
    best: _RawMatch | None = None
    for pattern in patterns:
        m = pattern.regex.search(line)
        if m is None:
            continue
        candidate = _RawMatch(
            start=m.start("ts"),
            end=m.end("ts"),
            text=m.group("ts"),
            pattern_name=pattern.name,
            normalize=pattern.normalize,
        )
        if best is None:
            best = candidate
            continue
        if candidate.start < best.start:
            best = candidate
        elif candidate.start == best.start and (
            candidate.end - candidate.start
        ) > (best.end - best.start):
            best = candidate
    return best


def _parse_timestamp(text: str, default: datetime) -> datetime | None:
    """切り出したタイムスタンプ文字列を実際の日時にパースする。

    年など文字列に含まれない項目は ``default`` の値で補う
    (例: BSD syslog形式は年を含まないため、実行時に指定された
    既定年で補完する)。
    """
    try:
        return dateutil_parser.parse(text, default=default)
    except (ValueError, OverflowError, TypeError):
        return None


class LineTagger:
    """ファイル(またはstdin)を1行ずつ処理し、変換後タイムスタンプを付与する。

    タイムスタンプが見つからない行は、直前に見つかったタイムスタンプの
    変換結果を引き継いで出力する(まだ一度も見つかっていない場合は空欄)。
    これはスタックトレースの継続行など、タイムスタンプを持たない行が
    ログに混在するケースを想定した挙動。
    """

    def __init__(
        self,
        output_format: str,
        default_datetime: datetime,
        patterns: list[PatternSpec] | None = None,
    ) -> None:
        self._output_format = output_format
        self._default_datetime = default_datetime
        self._patterns = patterns if patterns is not None else CANDIDATE_PATTERNS
        self._last_formatted: str | None = None

    def tag_line(self, line: str) -> str:
        match = _find_earliest_match(line, self._patterns)
        if match is not None:
            dt = _parse_timestamp(match.normalize(match.text), self._default_datetime)
            if dt is not None:
                self._last_formatted = dt.strftime(self._output_format)

        formatted = self._last_formatted if self._last_formatted is not None else ""
        return f"{formatted}\t{line}"
