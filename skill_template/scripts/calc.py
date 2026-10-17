"""calc.py — 計算エンジン。論文の式で、入力 → 出力（単位つき）を計算する。標準ライブラリだけ。

使い方:
  python calc.py --json "{\"L\": 0.5}"
  python calc.py --file inputs.json
  （ほかの Python から）from calc import calculate; calculate({"L": 0.5})

★ ひな形: 例として「片側が閉じた管の 1 次共鳴 f = c / (4L)」を入れてある。論文の式に置き換えること。
  入力は SI 単位で受ける。出力は value（SI）と display（人が読む表示）を返す。
"""
from __future__ import annotations

import argparse
import json
import math
import sys

SOURCE = "（ここに出典: 著者 年『題名』式の番号・ページ）"

# 入力: 名前 → 単位（SI）・説明・既定値（無ければ None = 必須）・適用範囲（無ければ None）
INPUTS = {
    "L": {"unit": "m", "label": "管の長さ", "default": None, "range": (0.01, 10.0)},
    "c": {"unit": "m/s", "label": "音速", "default": 343.0, "range": (300.0, 360.0)},
}

# 出力: 名前 → 単位（SI）・説明
OUTPUTS = {
    "f": {"unit": "Hz", "label": "1 次共鳴周波数"},
}


class InputError(Exception):
    pass


def _read(inputs: dict) -> tuple[dict, list[str]]:
    """入力を数に直し、既定値を補い、適用範囲を外れたら警告を足す。"""
    vals, warnings = {}, []
    for name, spec in INPUTS.items():
        v = inputs.get(name, spec["default"])
        if v is None:
            raise InputError(f"入力 {name}（{spec['label']} [{spec['unit']}]）がありません")
        try:
            v = float(v)
        except (TypeError, ValueError):
            raise InputError(f"入力 {name} が数ではありません: {v!r}")
        if not math.isfinite(v):
            raise InputError(f"入力 {name} が有限の数ではありません")
        lo_hi = spec.get("range")
        if lo_hi and not (lo_hi[0] <= v <= lo_hi[1]):
            warnings.append(f"適用範囲外: {name} = {v:g} {spec['unit']}（範囲 {lo_hi[0]:g}〜{lo_hi[1]:g}）")
        vals[name] = v
    unknown = sorted(set(inputs) - set(INPUTS))
    if unknown:
        warnings.append(f"使わない入力: {', '.join(unknown)}")
    return vals, warnings


def calculate(inputs: dict) -> dict:
    v, warnings = _read(inputs)
    # ---- ここから論文の式 ----
    f = v["c"] / (4.0 * v["L"])                      # 式(1)
    # ---- ここまで ----
    return {
        "outputs": {"f": {"value": f, "unit": "Hz", "display": f"{f:.1f} Hz"}},
        "equation": "式(1) f = c / (4L)",
        "source": SOURCE,
        "warnings": warnings,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--json", help="入力の JSON")
    g.add_argument("--file", help="入力の JSON ファイル")
    a = ap.parse_args(argv)
    try:
        if a.json:
            data = json.loads(a.json)
        else:
            with open(a.file, encoding="utf-8") as fp:
                data = json.load(fp)
        out = calculate(data.get("inputs", data))
    except (InputError, ValueError, OSError) as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        return 2
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
