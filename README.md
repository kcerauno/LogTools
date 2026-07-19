# wk_logtool

ログ解析用の単機能CLIツール群を集めたプロジェクトです。ツールごとに
`src/wk_logtool/<ツール名>/` 以下にまとめ、共通処理は
`src/wk_logtool/common/` に置きます。

現在含まれるツール:

- [`retime`](#retime) — ログファイルの日時フォーマットを識別し、変換後タイムスタンプを各行に付与する

## セットアップ

```bash
cd wk_logtool
python3 -m venv .venv        # 既に .venv がある場合は不要
source .venv/bin/activate
pip install -e ".[dev]"      # devを付けるとテスト用のpytestも入る
```

インストールすると `retime` コマンドが使えるようになります。

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

## テストの実行

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```
