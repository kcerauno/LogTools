"""段階的な時刻丸め(粗視化)レベルの定義。

大量のログから「変化が起きたと思われる時間帯」を絞り込むため、タイムスタンプを
段階的に丸めてグルーピングし、件数を数えるための丸めレベル一覧。
細かい方(ミリ秒)から粗い方(年月)へ、1段階ずつ精度を落としていく。
最も粗い"date"レベルでも年月(YYYYMM)は残り、それ以上は丸めない。

各レベルは、指定した粒度**以下**を切り捨てる(それより細かい情報は
すべて失われる)。例えば "hour" レベルは時・分・秒・ミリ秒をすべて0にし、
日付単位でグルーピングする。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Level:
    name: str
    description: str
    #: タイムスタンプを、このレベルの粒度に丸め込む関数。
    truncate: Callable[[datetime], datetime]
    #: 丸めた結果を表示するためのstrftimeフォーマット。
    display_format: str


def _floor10(value: int) -> int:
    return (value // 10) * 10


LEVELS: list[Level] = [
    Level(
        name="ms",
        description="ミリ秒(マイクロ秒)を丸める",
        truncate=lambda dt: dt.replace(microsecond=0),
        display_format="%Y%m%d %a %H:%M:%S",
    ),
    Level(
        name="sec1",
        description="秒の1桁目(1の位)以下を丸める(10秒単位)",
        truncate=lambda dt: dt.replace(second=_floor10(dt.second), microsecond=0),
        display_format="%Y%m%d %a %H:%M:%S",
    ),
    Level(
        name="sec2",
        description="秒の2桁目(10の位)以下を丸める(分単位)",
        truncate=lambda dt: dt.replace(second=0, microsecond=0),
        display_format="%Y%m%d %a %H:%M",
    ),
    Level(
        name="min1",
        description="分の1桁目(1の位)以下を丸める(10分単位)",
        truncate=lambda dt: dt.replace(
            minute=_floor10(dt.minute), second=0, microsecond=0
        ),
        display_format="%Y%m%d %a %H:%M",
    ),
    Level(
        name="min2",
        description="分の2桁目(10の位)以下を丸める(時間単位)",
        truncate=lambda dt: dt.replace(minute=0, second=0, microsecond=0),
        display_format="%Y%m%d %a %H",
    ),
    Level(
        name="hour",
        description="時間以下を丸める(日単位、曜日も表示)",
        truncate=lambda dt: dt.replace(
            hour=0, minute=0, second=0, microsecond=0
        ),
        display_format="%Y%m%d %a",
    ),
    Level(
        name="weekday",
        description="曜日以下を丸める(日付のみ)",
        truncate=lambda dt: dt.replace(
            hour=0, minute=0, second=0, microsecond=0
        ),
        display_format="%Y%m%d",
    ),
    Level(
        name="date",
        description="日付(日にち)以下を丸める(月単位。年月のみ残す、最も粗いレベル)",
        truncate=lambda dt: dt.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        ),
        display_format="%Y%m",
    ),
]

LEVEL_NAMES: list[str] = [lvl.name for lvl in LEVELS]

_BY_NAME = {lvl.name: lvl for lvl in LEVELS}


def get_level(name: str) -> Level:
    return _BY_NAME[name]
