---
name: __NAME__
description: "（いつ使うか。例: 〇〇の値を、著者 年 の式で計算・検査するとき）"
---

# __NAME__

（何を計算する skill か、1〜2 文）

## 式

$$ f = \frac{c}{4L} $$

- $f$: 1 次共鳴周波数 [Hz]、$c$: 音速 [m/s]（既定 343）、$L$: 管の長さ [m]
- 出典: （著者 年『題名』式(1)、p.○）

## 入力と適用範囲

| 名前 | 意味 | 単位（SI） | 既定値 | 適用範囲 |
|---|---|---|---|---|
| L | 管の長さ | m | （必須） | 0.01〜10 |
| c | 音速 | m/s | 343 | 300〜360 |

範囲を外れると calc.py が `warnings` を返す。そのときは答えに必ず書き添える。

## 使い方

スクリプトは `${CLAUDE_SKILL_DIR}/scripts/`（チャットでは SKILL.md から見た `scripts/`）にある。

1. 計算: `python3 ${CLAUDE_SKILL_DIR}/scripts/calc.py --json '{"L": 0.5}'` → `outputs.f.display` を答える
2. 検査（実測や論文の値と比べる）: `python3 ${CLAUDE_SKILL_DIR}/scripts/check.py --json '{"cases": [{"inputs": {"L": 0.5}, "expected": {"f": 170}}]}'`
   - CSV: `python3 ${CLAUDE_SKILL_DIR}/scripts/check.py --csv 測定.csv --map '{"Frequency (Hz)": "f"}' --rel 0.05`
   - 論文の値での検算: `python3 ${CLAUDE_SKILL_DIR}/scripts/check.py --file ${CLAUDE_SKILL_DIR}/examples.json`
3. 答えには必ず出典を書く（例: 「著者 年 の式(1) による」）。`warnings`・`causes` があれば添える
4. 式の値は自分で暗算せず、必ず calc.py を実行して出す

## CSV の列名の対応

| よくある列名 | 名前 |
|---|---|
| （例）Frequency (Hz) | f |
