# 変更履歴

版の付け方: `MAJOR.MINOR.PATCH`（manifest.json の `version`）。
MAJOR = カード・skill の形を壊す変更 / MINOR = 機能の追加 / PATCH = 不具合の修正。

## 0.3.0 — 2026-10-17
### 追加
- 引用の書き出し: 一覧に出ている論文を BibTeX（`export/references.bib`）か参考文献の一覧（`references.md`）に。上書きしない。中身はコピーもする
- 引用キーは英数字（名字＋年＋題名の最初の語。日本語の名前は `ref2021`）。同じキーは a, b … で分ける
- README（英日）・LICENSE（PolyForm Noncommercial 1.0.0）・画面の画像
### 直したこと
- メニューのアイコンが名前の文字のまま出ていた

## 0.2.0 — 2026-10-17
### 追加
- エンジン（Claude の skill）: カードの「エンジンを作る…」でひな形 `skills/<名前>/`（SKILL.md・scripts/calc.py・scripts/check.py・examples.json・README.md）
- check.py はひな形のまま使える（calc.py の INPUTS / OUTPUTS を見る）。CSV（列名の読み替え）、許容差、原因の候補
- 検算: 動かす前に ast で検査 → 初回は確かめる → 別プロセス・skill のフォルダ・10 秒。通るとハッシュを `.verified.json` に。中身が変わったら zip は作れない
- zip（`export/<名前>.zip`、中は `<名前>/SKILL.md …`）
- 「論文 / エンジン」の切り替え、エンジンの一覧
- `LAB_FORMAT.md` にエンジンの書き方

## 0.1.0 — 2026-10-17
### 追加
- PDF → カード: 1 ページ目と埋め込み情報から題名・著者・年・DOI を推定（オフライン）。取り込む前に小窓で直せる。コピー / 移動。同じ PDF を知らせる
- フォルダに直接入れた PDF を「カードの無い PDF」として出す
- 一覧（さがす・状態・タグ・年）、カード（書誌・タグ・状態、PDF を開く、名前を変える、Claude に頼む文）
- 外（Claude）で書き換えたら読み直す
- `LAB_FORMAT.md`（カードの書き方）
