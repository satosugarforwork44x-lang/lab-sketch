# LAB_FORMAT — Lab Sketch のカードの書き方（Claude 向け）

このフォルダは Hub の拡張「Lab Sketch」が使う。論文 1 本 = `papers/` の md 1 枚（カード）。
Lab Sketch はこのファイルを自動で置き直すので、ここは書き換えないこと。

```
Lab Sketch/
  LAB_FORMAT.md        … この説明
  papers/<名前>.pdf     … 論文
  papers/<名前>.md      … カード（下の形）
  skills/<skill名>/     … 計算・検査エンジン（skill）
  export/              … 登録用の zip・BibTeX（Lab Sketch が作る）
```

## カードの形

```markdown
---
title: "Diffraction Loss at the Baffle Edge"
authors: ["John Smith", "Akiko Tanaka"]
year: 2024
doi: "10.1121/1.1234567"
pdf: "2024_Smith_DiffractionLoss.pdf"
source: "smith2024.pdf"
tags: ["スピーカー", "バッフル"]
status: unread
skills: ["baffle-step"]
added: 2026-10-17
---

## 要約

## 手法

## 結論

## 式・数値（エンジンの元）

## 自分のメモ
```

### front matter の決まり（Lab Sketch は YAML の一部しか読まない）

- 1 行に `キー: 値`。値は `"文字"`（JSON と同じ書き方）・整数・`["a", "b"]` の一覧のどれか
- 複数行の文字（`|` `>`）・入れ子は**使わない**（読めずにエラーになる）
- `status` は `unread`（未読）/ `read`（読んだ）/ `cite`（引用する）のどれか
- `pdf` は同じフォルダの PDF のファイル名。**書き換えない**（名前を変えるのは Lab Sketch の画面から）
- `source`（元のファイル名）・`added`（取り込んだ日）は変えない
- 書誌（title・authors・year・doi）は PDF から推定した値で、外れていることがある。PDF を読んで違っていたら直してよい
- 知らないキーを足してもよい（Lab Sketch は消さずに残す）

### 本文（Claude が書く所）

「この論文をまとめて」と頼まれたら、PDF を読んで次の節に書く。見出しの名前と順番は変えない（英語の見出し `Summary / Method / Conclusions / Equations & values (engine source) / My notes` のカードもある。その場合は英語の見出しのまま）。

| 節 | 書くこと |
|---|---|
| 要約 | 3〜5 文。何を明らかにした論文か |
| 手法 | 実験・解析・シミュレーションの方法、条件（試料・周波数範囲・装置など） |
| 結論 | 主な結果。数値があれば単位つきで |
| 式・数値（エンジンの元） | 計算エンジンにできる式を、**式の番号・ページ**つきで。記号の意味と単位、適用範囲。表や図から読める値（検算に使える物）も |
| 自分のメモ | **利用者の欄。Claude は書かない**（頼まれたときだけ） |

- 式は LaTeX（`$...$`）で書き、言葉の説明も添える
- 推測は「（推測）」と書いて区別する。論文に無いことを論文の主張として書かない
- 書き換えるのは頼まれた節だけ。front matter と他の節はそのまま残す

---

## エンジン（skill）の書き方

「この論文の式をエンジンにして」と頼まれたら、`skills/<skill名>/` を書く。Lab Sketch の「エンジンを作る…」で作ったひな形があれば、それを直す。

```
skills/<skill名>/
  SKILL.md            … Claude の skill の本体（下の決まり）
  scripts/calc.py     … 計算エンジン
  scripts/check.py    … 検査エンジン（ひな形のまま使える。直さなくてよい）
  examples.json       … 論文の表・図から取った検算の値
  README.md           … 人が読む説明（出典・適用範囲）
```

### 名前と単位

- **1 つのテーマに 1 つ**（例 `baffle-step`）。論文 1 本ごとに作らない。同じテーマの別の論文の式は、同じ skill に足して出典を並べる
- skill名は英小文字・数字・ハイフン、64 字まで。フォルダ名と SKILL.md の `name` を同じにする
- カードの `skills` にこの名前を入れる（出典の論文がどれか分かるように）

### SKILL.md

- 先頭に `name` と `description`（**いつ使うか**を 1〜2 文。1024 字まで。例: 「スピーカーのバッフルステップの周波数を、Smith 2024 の式で計算・検査するとき」）
- 本文: 何を計算するか・式（LaTeX と言葉で）・入力の表（名前・意味・SI 単位・既定値・適用範囲）・出典（論文名・式の番号・ページ）・使い方
- スクリプトは `python3 ${CLAUDE_SKILL_DIR}/scripts/calc.py --json '{…}'` の形で書く
- 「答えには必ず出典を書く」「式の値は暗算せず calc.py を実行する」「warnings があれば添える」を書いておく

### scripts/calc.py

- `calculate(inputs: dict) -> dict` と、`--json` / `--file` で動く入口（ひな形のまま）
- `INPUTS`（名前 → 単位・説明・既定値・適用範囲）と `OUTPUTS` を書き、式は `calculate` の中の「ここから論文の式」の間に
- 入力は **SI 単位**。返すのは `{"outputs": {名前: {"value": SI の値, "unit", "display": 人が読む表示}}, "equation", "source", "warnings"}`
- `SOURCE` に出典を書く（ひな形の「（ここに出典…」のままだと警告）

### examples.json（検算の値）

- **論文の表・図・本文の数値例から取る**。自分で計算した値を入れない（それでは検算にならない）
- `cases` の各項目に `name`・`source`（「表2 の 3 行目」「図5 から読んだ値」）・`inputs`・`expected`
- `tolerance` は論文に書かれた誤差。図から読んだ値は読み取りの誤差を見込む（例 `{"rel": 0.05}`）

### Lab Sketch が止めるもの（書かないこと）

検算は利用者の PC で動くので、動かす前にコードを調べて、次の物があれば止める:

- 決めた一覧に無い import（`socket` `urllib` `requests` `subprocess` `os` `shutil` `ctypes` など。使えるのは `math` `cmath` `statistics` `json` `csv` `argparse` `sys` `pathlib` `re` `dataclasses` `typing` `enum` `functools` `itertools` `collections` `fractions` `decimal` `datetime` など。`numpy` は使えるが、PC に入っていないと動かないので SKILL.md に書く）
- `eval` `exec` `compile` `__import__`、書き込みの `open`、`.write_text()` `.unlink()` `.mkdir()` など
- 10 秒で終わらない計算

検算が通ると `.verified.json` ができる（Lab Sketch が書く。触らない）。中身を直したら、もう一度検算するまで zip は作れない。
