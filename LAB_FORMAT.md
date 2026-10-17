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
