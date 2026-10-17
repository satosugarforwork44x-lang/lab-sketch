"""check.py — 検査エンジン。実測値や論文の値を calc.py の結果と比べて、合否を出す。標準ライブラリだけ。

使い方:
  python check.py --file examples.json                       … 論文の表・図の値で検算
  python check.py --json "{\"cases\": [...], \"tolerance\": {...}}"
  python check.py --csv measured.csv [--map "{\"列名\": \"入力か出力の名前\"}"] [--rel 0.05]

入力の形:
  {"tolerance": {"default": {"rel": 0.02}, "f": {"abs": 1.0}},          … 許容差（rel は割合、abs は SI 単位の差）
   "cases": [{"name": "表2 の1行目", "inputs": {"L": 0.5}, "expected": {"f": 171.5}}]}
CSV: 1 行目が列名。入力の名前の列は入力、出力の名前の列は期待する値として読む（--map で列名を読み替え）。

★ ひな形のまま使える（calc.py の INPUTS / OUTPUTS を見て動く）。直すのは CAUSES の言葉くらい。
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import calc  # noqa: E402  同じフォルダの計算エンジン

DEFAULT_TOL = {"rel": 0.02}


def _tol(tolerance: dict, name: str) -> dict:
    t = (tolerance or {}).get(name) or (tolerance or {}).get("default") or DEFAULT_TOL
    return {k: float(v) for k, v in t.items() if k in ("rel", "abs")}


def _within(actual: float, expected: float, t: dict) -> bool:
    ok_abs = "abs" in t and abs(actual - expected) <= t["abs"]
    ok_rel = "rel" in t and abs(actual - expected) <= t["rel"] * max(abs(expected), 1e-300)
    return ok_abs or ok_rel


def _causes(results: list[dict]) -> list[str]:
    """外れ方から、考えられる原因の候補を挙げる（決めつけない）。"""
    bad = [r for r in results if not r["ok"]]
    out: list[str] = []
    if not bad:
        return out
    if any(r.get("warnings") for r in bad):
        out.append("適用範囲外の条件がある（calc の警告を見る）")
    ratios = [r["actual"] / r["expected"] for r in bad if r.get("expected") and r.get("actual") is not None]
    for k, why in ((1000, "単位の取り違え（k / m の付け忘れ）"), (100, "単位の取り違え（cm と m など）"), (10, "単位の取り違え（桁）"),
                   (2 * math.pi, "角周波数 ω と周波数 f の取り違え"), (2, "直径と半径・片側と両側の取り違え")):
        if ratios and all(abs(x / k - 1) < 0.03 or abs(x * k - 1) < 0.03 for x in ratios):
            out.append(f"どの条件も約 {k:g} 倍ずれている → {why}")
            break
    diffs = [r["diff_pct"] for r in bad if r.get("diff_pct") is not None]
    if len(diffs) >= 2 and (all(d > 0 for d in diffs) or all(d < 0 for d in diffs)) and not out:
        out.append("どれも同じ向きにずれている → 測定条件の違い（温度・取り付け・校正）か、式の係数")
    if not out:
        out.append("ずれの向きがばらばら → 測定のばらつき、または許容差が厳しすぎる")
    return out


def check(cases: list[dict], tolerance: dict | None = None) -> dict:
    results = []
    for i, case in enumerate(cases or []):
        name = case.get("name") or f"#{i + 1}"
        try:
            out = calc.calculate(case.get("inputs", {}))
        except calc.InputError as e:
            results.append({"case": name, "ok": False, "error": str(e)})
            continue
        for key, expected in (case.get("expected") or {}).items():
            if key not in out["outputs"]:
                results.append({"case": name, "output": key, "ok": False, "error": f"calc に出力 {key} がありません"})
                continue
            actual, expected = float(out["outputs"][key]["value"]), float(expected)
            t = _tol(tolerance, key)
            diff = actual - expected
            results.append({"case": name, "output": key, "unit": out["outputs"][key].get("unit", ""),
                            "expected": expected, "actual": actual, "diff": diff,
                            "diff_pct": (diff / expected * 100) if expected else None,
                            "tolerance": t, "ok": _within(actual, expected, t), "warnings": out.get("warnings", [])})
    ng = sum(1 for r in results if not r["ok"])
    return {"pass": bool(results) and ng == 0, "summary": {"total": len(results), "ok": len(results) - ng, "ng": ng},
            "results": results, "causes": _causes(results), "source": calc.SOURCE}


def read_csv(path: str, mapping: dict | None = None) -> list[dict]:
    mapping = mapping or {}
    cases = []
    with open(path, encoding="utf-8-sig", newline="") as fp:
        for n, row in enumerate(csv.DictReader(fp), 2):
            ins, exp = {}, {}
            for col, val in row.items():
                key = mapping.get(col, col)
                if val is None or str(val).strip() == "":
                    continue
                if key in calc.INPUTS:
                    ins[key] = float(val)
                elif key in calc.OUTPUTS:
                    exp[key] = float(val)
            cases.append({"name": f"{Path(path).name} {n} 行目", "inputs": ins, "expected": exp})
    return cases


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--json")
    g.add_argument("--file")
    g.add_argument("--csv")
    ap.add_argument("--map", help="CSV の列名 → 入力・出力の名前（JSON）")
    ap.add_argument("--rel", type=float, help="許容差（割合）。指定するとすべての出力に使う")
    a = ap.parse_args(argv)
    try:
        if a.csv:
            data = {"cases": read_csv(a.csv, json.loads(a.map) if a.map else None)}
        elif a.json:
            data = json.loads(a.json)
        else:
            with open(a.file, encoding="utf-8") as fp:
                data = json.load(fp)
        tol = {"default": {"rel": a.rel}} if a.rel is not None else data.get("tolerance")
        out = check(data.get("cases", []), tol)
    except (ValueError, OSError, KeyError) as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        return 2
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
