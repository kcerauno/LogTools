"""coarsen: retimeの出力(先頭タイムスタンプ付きログ)を、指定した粒度で
段階的に丸めてグルーピングし、件数を数えるCLIツール。

大量のログから「変化が起きたと思われる時間帯」を絞り込むために使う。
粗い粒度(date, weekdayなど)から始めて件数の偏りを見つけ、該当範囲だけ
`grep`等で絞り込みつつ、より細かい粒度(hour, min1, ...)で再実行して
時間帯を絞り込んでいく、という反復的な使い方を想定している。

出力形式: ``<件数>\\t<丸めたタイムスタンプ>`` (丸めたタイムスタンプの昇順)
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable

from wk_logtool.common.cli_io import no_piped_input, open_binary_sources
from wk_logtool.common.text_encoding import decode_line

from .aggregator import count_by_level
from .levels import (
    DEFAULT_DAY_START_HOUR,
    DEFAULT_NIGHT_START_HOUR,
    LEVEL_NAMES,
    get_level,
    make_daynight_level,
)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="coarsen",
        description=(
            "retimeの出力(先頭に'<タイムスタンプ>\\t'が付いたログ)を読み、"
            "指定した粒度でタイムスタンプを丸めてグルーピングし、"
            "'<件数>\\t<丸めたタイムスタンプ>' の形式で件数を集計する。"
        ),
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="対象ログファイル(複数指定可)。省略時または'-'で標準入力を読む。",
    )
    parser.add_argument(
        "--level",
        required=True,
        choices=LEVEL_NAMES,
        help=(
            "丸めの粒度。細かい順に: "
            "ms(ミリ秒切り捨て), sec1(秒を10秒単位に丸め), "
            "sec2(秒を切り捨て), min1(分を10分単位に丸め), "
            "min2(分を切り捨て), daynight(day/nightの2区分に丸める), "
            "hour(時を切り捨て、日単位), "
            "weekday(曜日非表示の日単位), date(全件を1グループに集約)。"
        ),
    )
    parser.add_argument(
        "--day-start-hour",
        type=int,
        default=DEFAULT_DAY_START_HOUR,
        metavar="H",
        help=(
            "--level daynight のときのみ有効。dayの開始時刻(0-23、"
            f"デフォルト{DEFAULT_DAY_START_HOUR})。"
        ),
    )
    parser.add_argument(
        "--night-start-hour",
        type=int,
        default=DEFAULT_NIGHT_START_HOUR,
        metavar="H",
        help=(
            "--level daynight のときのみ有効。nightの開始時刻(0-23、"
            f"デフォルト{DEFAULT_NIGHT_START_HOUR})。"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if no_piped_input(args.files):
        parser.print_usage(sys.stderr)
        print(
            "coarsen: エラー: 対象ファイルが指定されておらず、"
            "標準入力からの入力もありません。"
            "ファイルを指定するか、パイプで標準入力に渡してください。",
            file=sys.stderr,
        )
        return 2

    if args.level == "daynight":
        try:
            level = make_daynight_level(args.day_start_hour, args.night_start_hour)
        except ValueError as exc:
            parser.print_usage(sys.stderr)
            print(f"coarsen: エラー: {exc}", file=sys.stderr)
            return 2
    else:
        level = get_level(args.level)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    def _decoded_lines() -> Iterable[str]:
        for _path, raw_lines in open_binary_sources(args.files):
            for raw in raw_lines:
                yield decode_line(raw)

    for bucket_dt, count in count_by_level(_decoded_lines(), level):
        print(f"{count}\t{level.format(bucket_dt)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
