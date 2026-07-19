"""1行(バイト列)単位で文字コードを判定しUTF-8文字列へ変換するユーティリティ。

同一ファイル内にEUC-JP/Shift_JIS/UTF-8が混在するログを想定し、行ごとに
判定する。ファイル全体に対して単一のエンコーディングを仮定しない。
"""

from __future__ import annotations

from charset_normalizer import from_bytes

#: 判定候補。日本語ログでよく使われる3種類に限定することで、
#: 短い行でも判定精度を上げる(候補を広げるほど短文での誤判定が増える)。
DEFAULT_CANDIDATES: tuple[str, ...] = ("utf_8", "shift_jis", "euc_jp")


def decode_line(raw: bytes, candidates: tuple[str, ...] = DEFAULT_CANDIDATES) -> str:
    """1行分のバイト列を、候補エンコーディングの中から判定してデコードする。

    まずUTF-8として厳密デコードを試みる(ログの大半はUTF-8かASCIIのため高速)。
    失敗した場合のみ charset-normalizer で候補間の判定を行う。
    どの候補でも決定できない場合は、置換文字付きでUTF-8デコードする
    (行単位処理のため、1行のデコード不能でツール全体を止めない)。
    """
    if not raw:
        return ""

    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        pass

    result = from_bytes(raw, cp_isolation=list(candidates)).best()
    if result is not None:
        return str(result)

    return raw.decode("utf-8", errors="replace")
