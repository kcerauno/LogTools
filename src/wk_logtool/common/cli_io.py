"""複数のCLIツールで共通して使う、ファイル/標準入力の行読み込みユーティリティ。

対象ファイル(複数可)または標準入力から、改行を除いたバイト列を1行ずつ
取り出す。ファイル未指定かつ標準入力もパイプされていない(端末から直接
実行された)場合の検出も提供する。
"""

from __future__ import annotations

import sys
from collections.abc import Iterable, Iterator


def strip_newline(raw: bytes) -> bytes:
    if raw.endswith(b"\n"):
        raw = raw[:-1]
    if raw.endswith(b"\r"):
        raw = raw[:-1]
    return raw


def iter_raw_lines(stream: object) -> Iterator[bytes]:
    for raw in stream:  # type: ignore[attr-defined]
        yield strip_newline(raw)


def open_binary_sources(paths: list[str]) -> Iterable[tuple[str, Iterable[bytes]]]:
    """対象ファイル群(または標準入力)を順に開き、(パス, 行イテレータ)を返す。

    ファイル未指定、または"-"のみの指定なら標準入力を読む。
    """
    if not paths or paths == ["-"]:
        yield "-", iter_raw_lines(sys.stdin.buffer)
        return
    for path in paths:
        if path == "-":
            yield "-", iter_raw_lines(sys.stdin.buffer)
            continue
        with open(path, "rb") as f:
            yield path, iter_raw_lines(f)


def no_piped_input(files: list[str]) -> bool:
    """ファイル指定がなく、標準入力もパイプされていない(端末)場合にTrueを返す。

    このケースで標準入力からの読み込みを試みると、入力待ちでハングしてしまう
    ため、呼び出し側でエラー表示して終了するために使う。
    """
    return not files and sys.stdin.isatty()
