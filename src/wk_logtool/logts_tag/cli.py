"""logts-tag: ログファイルの日時フォーマットを識別し、変換後タイムスタンプを
各行の先頭に付与するCLIツール。

出力形式: ``<変換後タイムスタンプ>\\t<ログ原文>``

対応する問題点:
  - タイムスタンプが存在しない行 -> 直前のタイムスタンプを引き継いで出力
  - ファイル/行ごとに日時フォーマットがまちまち -> 既知フォーマット群への
    行ごと総当りマッチ + dateutilによる解釈
  - 同一行に複数のタイムスタンプ -> 先に出現したものを採用
  - EUC-JP/Shift_JIS/UTF-8混在 -> 行単位で自動判定しUTF-8へ統一して出力
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable, Iterator
from datetime import datetime

from wk_logtool.common.text_encoding import decode_line

from .tagger import LineTagger

DEFAULT_OUTPUT_FORMAT = "%Y%m%d %H:%M:%S.%f"


def _strip_newline(raw: bytes) -> bytes:
    if raw.endswith(b"\n"):
        raw = raw[:-1]
    if raw.endswith(b"\r"):
        raw = raw[:-1]
    return raw


def _iter_raw_lines(stream: object) -> Iterator[bytes]:
    for raw in stream:  # type: ignore[attr-defined]
        yield _strip_newline(raw)


def _open_binary_sources(paths: list[str]) -> Iterable[tuple[str, Iterable[bytes]]]:
    if not paths or paths == ["-"]:
        yield "-", _iter_raw_lines(sys.stdin.buffer)
        return
    for path in paths:
        if path == "-":
            yield "-", _iter_raw_lines(sys.stdin.buffer)
            continue
        with open(path, "rb") as f:
            yield path, _iter_raw_lines(f)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="logts-tag",
        description=(
            "ログファイルの日時フォーマットを識別し、各行の先頭に"
            "'<変換後タイムスタンプ>\\t<ログ原文>' の形式で付与して標準出力に出す。"
        ),
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="対象ログファイル(複数指定可)。省略時または'-'で標準入力を読む。",
    )
    parser.add_argument(
        "--output-format",
        default=DEFAULT_OUTPUT_FORMAT,
        help=(
            "変換後タイムスタンプのstrftimeフォーマット"
            f"(既定値: {DEFAULT_OUTPUT_FORMAT!r})。"
        ),
    )
    parser.add_argument(
        "--default-year",
        type=int,
        default=None,
        help=(
            "タイムスタンプ文字列に年が含まれない場合(BSD syslog形式など)に"
            "補完する年。省略時は実行時点の年を使う。"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if not args.files and sys.stdin.isatty():
        parser.print_usage(sys.stderr)
        print(
            "logts-tag: エラー: 対象ファイルが指定されておらず、"
            "標準入力からの入力もありません。"
            "ファイルを指定するか、パイプで標準入力に渡してください。",
            file=sys.stderr,
        )
        return 2

    year = args.default_year if args.default_year is not None else datetime.now().year
    default_datetime = datetime(year=year, month=1, day=1)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    for _path, raw_lines in _open_binary_sources(args.files):
        tagger = LineTagger(
            output_format=args.output_format,
            default_datetime=default_datetime,
        )
        for raw in raw_lines:
            line = decode_line(raw)
            print(tagger.tag_line(line))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
