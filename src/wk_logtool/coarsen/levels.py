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
from datetime import datetime, timedelta


@dataclass(frozen=True)
class Level:
    name: str
    description: str
    #: タイムスタンプを、このレベルの粒度に丸め込む関数。
    truncate: Callable[[datetime], datetime]
    #: 丸めた結果を表示するためのstrftimeフォーマット。
    display_format: str
    #: 設定時は display_format の代わりにこちらで表示文字列を組み立てる
    #: (daynightレベルのように"day"/"night"ラベルを付与する場合に使う)。
    format_bucket: Callable[[datetime], str] | None = None

    def format(self, dt: datetime) -> str:
        if self.format_bucket is not None:
            return self.format_bucket(dt)
        return dt.strftime(self.display_format)


def _floor10(value: int) -> int:
    return (value // 10) * 10


#: dayの開始時刻・nightの開始時刻のデフォルト値。
DEFAULT_DAY_START_HOUR = 7
DEFAULT_NIGHT_START_HOUR = 22


def make_daynight_level(
    day_start_hour: int = DEFAULT_DAY_START_HOUR,
    night_start_hour: int = DEFAULT_NIGHT_START_HOUR,
) -> Level:
    """day(``day_start_hour``時〜``night_start_hour``時)/night(その逆)の
    2区分に丸めるレベルを作る。

    nightは日をまたぐ範囲(例: 22時〜翌7時)になり得るが、日付は
    「nightが開始した時点の日付」を使う。つまり0時台〜``day_start_hour``時
    未満のタイムスタンプは、前日のnight(前日の``night_start_hour``時に
    開始したnight)としてグルーピングする。
    """
    if not (0 <= day_start_hour <= 23 and 0 <= night_start_hour <= 23):
        raise ValueError("day_start_hour/night_start_hourは0〜23で指定してください")
    if day_start_hour >= night_start_hour:
        raise ValueError("day_start_hourはnight_start_hourより小さい値にしてください")

    def _truncate(dt: datetime) -> datetime:
        if day_start_hour <= dt.hour < night_start_hour:
            return dt.replace(hour=day_start_hour, minute=0, second=0, microsecond=0)
        if dt.hour >= night_start_hour:
            return dt.replace(hour=night_start_hour, minute=0, second=0, microsecond=0)
        # dt.hour < day_start_hour: 前日のnight(0時をまたいで継続中)に属する。
        prev_date = dt - timedelta(days=1)
        return prev_date.replace(
            hour=night_start_hour, minute=0, second=0, microsecond=0
        )

    def _format(dt: datetime) -> str:
        label = "day" if dt.hour == day_start_hour else "night"
        return f"{dt.strftime('%Y%m%d %a')} {label}"

    return Level(
        name="daynight",
        description=(
            f"day({day_start_hour}時〜{night_start_hour}時)/"
            f"night({night_start_hour}時〜{day_start_hour}時)の2区分に丸める"
            "(日付はnightが開始した日を使う)"
        ),
        truncate=_truncate,
        display_format="%Y%m%d %a",
        format_bucket=_format,
    )


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
    make_daynight_level(),
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
