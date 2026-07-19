# wk_logtool

ログ解析用の単機能CLIツール群を集めたプロジェクトです。ツールごとに
`src/wk_logtool/<ツール名>/` 以下にまとめ、共通処理は
`src/wk_logtool/common/` に置きます。

現在含まれるツール:

- [`retime`](#retime) — ログファイルの日時フォーマットを識別し、変換後タイムスタンプを各行に付与する
- [`coarsen`](#coarsen) — `retime`の出力を、指定した粒度で段階的に丸めてグルーピングし件数を集計する(変化が起きた時間帯の絞り込み用)

## セットアップ

```bash
cd wk_logtool
python3 -m venv .venv        # 既に .venv がある場合は不要
source .venv/bin/activate
pip install -e ".[dev]"      # devを付けるとテスト用のpytestも入る
```

インストールすると `retime` / `coarsen` コマンドが使えるようになります。

---

## retime

対象ログファイルの一部を見て日時フォーマットを識別し、各行の先頭に

```
<変換後タイムスタンプ>\t<ログ原文>
```

という形式でタブ区切り出力するツールです。

### 基本の使い方

```bash
retime access.log
```

複数ファイルを指定すると順番に処理します(タイムスタンプなし行の
引き継ぎ状態はファイルをまたいでリセットされます)。

```bash
retime access1.log access2.log
```

標準入力からも読めます(パイプ処理向け)。

```bash
tail -f app.log | retime
cat app.log | retime -
```

ファイル指定がなく、標準入力もパイプされていない(端末から直接実行した)
場合は、入力待ちでハングせずにエラーメッセージと使い方を表示して
終了コード2で終了します。

```bash
$ retime
usage: retime [-h] [--output-format OUTPUT_FORMAT]
              [--default-year DEFAULT_YEAR]
              [files ...]
retime: エラー: 対象ファイルが指定されておらず、標準入力からの入力もありません。ファイルを指定するか、パイプで標準入力に渡してください。
```

### オプション

| オプション | 説明 | 既定値 |
| --- | --- | --- |
| `--output-format FORMAT` | 変換後タイムスタンプの `strftime` 書式 | `%Y%m%d %H:%M:%S.%f` |
| `--default-year YEAR` | タイムスタンプ文字列に年が含まれない場合(BSD syslog形式など)に補完する年 | 実行時点の年 |

```bash
# 出力フォーマットを変える
retime --output-format '%Y-%m-%d %H:%M:%S' app.log

# 2024年のアーカイブログ(syslog形式で年が書かれていない)を処理する場合
retime --default-year 2024 archive/syslog
```

### 実行例

入力ログ(`app.log`。実際は行ごとにフォーマットや文字コードが
バラバラでもよい):

```
2026-07-19T10:22:01.123456+09:00 [INFO] service started
  Traceback (most recent call last):
    File "app.py", line 10, in <module>
19/Jul/2026:10:22:05 +0900 GET /index.html 200
Jul 19 10:22:07 host01 sshd[123]: Accepted publickey for user
```

```bash
$ retime app.log
20260719 10:22:01.123456	2026-07-19T10:22:01.123456+09:00 [INFO] service started
20260719 10:22:01.123456	  Traceback (most recent call last):
20260719 10:22:01.123456	    File "app.py", line 10, in <module>
20260719 10:22:05.000000	19/Jul/2026:10:22:05 +0900 GET /index.html 200
20260719 10:22:07.000000	Jul 19 10:22:07 host01 sshd[123]: Accepted publickey for user
```

タイムスタンプを含まない2〜3行目は、直前(1行目)のタイムスタンプを
引き継いで出力されます。

### 対応している日時フォーマット

行ごとに以下の候補すべてに総当りでマッチを試み、最も先に出現した
ものを採用します(実体は
[`src/wk_logtool/retime/patterns.py`](src/wk_logtool/retime/patterns.py))。

| 名前 | 例 |
| --- | --- |
| `iso8601` | `2026-07-19T10:22:01.123456+09:00` |
| `apache_clf` | `19/Jul/2026:10:22:05 +0900` (Apache/nginx combined log format) |
| `slash_date` | `2026/07/19 10:22:01.500` |
| `dot_date` | `2026.07.19 10:22:01` |
| `compact_date` | `20260719 10:22:01.123456` |
| `us_date` | `07/19/2026 10:22:01` |
| `syslog_bsd` | `Jul 19 10:22:01` (年なし、`--default-year` で補完) |
| `oracle_alert_ctime` | `Sat Sep 03 15:31:58 2016` (Oracle Database Alert Log形式。`Sat Sep  3 ...` のようなスペース埋め日付にも対応) |

新しい書式を追加したい場合は `patterns.py` の `CANDIDATE_PATTERNS` に
正規表現を1つ追加するだけです。日付と時刻の区切りが特殊で
`dateutil` がそのままパースできない書式(Apache CLFなど)は、
`normalize` 関数で `dateutil` が解釈できる形に変換してから渡します。

### ログ解析ユースケースの4つの問題点への対応

1. **タイムスタンプが存在しない行がある**
   → 直前に見つかったタイムスタンプの変換結果を引き継いで出力します。
     まだ一度もタイムスタンプが出現していない場合は空欄になります。
2. **ログファイルごとに日時フォーマットがまちまち**
   → ファイル全体で1フォーマットに決め打ちせず、行ごとに既知フォーマット群へ
     総当りでマッチします。
3. **複数形式のタイムスタンプが同一ファイル(同一行)に混在する**
   → 行ごとに独立して判定するため複数形式混在ファイルでも問題なく、
     同一行に複数タイムスタンプがある場合は最も先に出現したものを採用します。
4. **EUC-JP、SJISとUTF-8の日本語文字列が同一ファイル内に混在する**
   → 1行ずつバイト列から文字コードを判定([`common/text_encoding.py`](src/wk_logtool/common/text_encoding.py))し、
     UTF-8に統一して出力します。

## coarsen

大量のログを調査するとき、まず粗い時間範囲で件数の偏りを見つけ、
そこから徐々に細かい粒度に絞り込んで「変化が起きたと思われる時間帯」を
特定していくためのツールです。`retime`の出力(`<タイムスタンプ>\t<ログ原文>`)
を読み、行頭のタイムスタンプを指定した粒度に丸めてグルーピングし、

```
<件数>\t<丸めたタイムスタンプ>
```

の形式で、丸めたタイムスタンプの昇順に出力します。

### 丸めの粒度(`--level`)

細かい方から粗い方へ、以下の8段階を用意しています(1回の実行で
指定できるのは1段階のみ)。

| `--level` | 意味 | `20091209 Wed 14:55:16` の丸め結果 |
| --- | --- | --- |
| `ms` | ミリ秒(マイクロ秒)を切り捨て | `20091209 Wed 14:55:16` |
| `sec1` | 秒を10秒単位に丸め(1の位を切り捨て) | `20091209 Wed 14:55:10` |
| `sec2` | 秒を切り捨て(分単位) | `20091209 Wed 14:55` |
| `min1` | 分を10分単位に丸め(1の位を切り捨て) | `20091209 Wed 14:50` |
| `min2` | 分を切り捨て(時間単位) | `20091209 Wed 14` |
| `hour` | 時を切り捨て(日単位、曜日表示あり) | `20091209 Wed` |
| `weekday` | 曜日も非表示にした日単位 | `20091209` |
| `date` | 日付も切り捨て、全件を1グループに集約 | (空文字。総件数の確認用) |

### 使い方

`retime`とパイプで組み合わせて使います。`retime`の出力形式によっては
曜日を含めておくと`coarsen`の表示が見やすくなります(`%a`)。

```bash
retime --output-format '%Y%m%d %a %H:%M:%S.%f' app.log | coarsen --level date
```

### 実行例(絞り込みの流れ)

`sample_data/ora_alert.log`(Oracle Database Alert Log)を例にすると:

```bash
$ retime --output-format '%Y%m%d %a %H:%M:%S.%f' sample_data/ora_alert.log | coarsen --level weekday
7	20091209
13	20160903

$ retime --output-format '%Y%m%d %a %H:%M:%S.%f' sample_data/ora_alert.log | coarsen --level min2
7	20091209 Wed 14
13	20160903 Sat 15

$ retime --output-format '%Y%m%d %a %H:%M:%S.%f' sample_data/ora_alert.log | coarsen --level ms
7	20091209 Wed 14:55:16
2	20160903 Sat 15:31:58
6	20160903 Sat 15:32:27
5	20160903 Sat 15:32:36
```

まず`weekday`で日付単位の偏りを見つけ、`min2`で時間帯を絞り込み、
最後に`ms`(または`sec1`など)で実際のタイムスタンプの塊を特定する、
という流れで調査できます。

ファイル指定がなく標準入力もパイプされていない場合の挙動、複数ファイル
指定への対応は`retime`と同様です。

## テストの実行

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```
