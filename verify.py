"""lab/verify.py — skill（計算・検査エンジン）の中身の検査・検算・zip。標準ライブラリだけ。

・Claude が書いたコードを PC で動かすので、自動では動かさない。利用者が中身を見てから「検算する」を押す
・動かす前に ast で検査する: import は決めた一覧の物だけ、ファイルを書く・消す・外部コマンド・eval などは止める
  （ネットにつなぐ道具は一覧に無いので import できない）。これは「うっかり」を止める物で、完全な隔離ではない
・実行は別プロセス（Hub と同じ Python、-E -B）、作業フォルダは skill のフォルダ、時間制限 10 秒
・検算が通ると、その時のファイルのハッシュを .verified.json に残す。中身が変わったら zip は作れない（もう一度検算する）
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import zipfile
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
REQUIRED = ("SKILL.md", "scripts/calc.py", "scripts/check.py", "examples.json")
STAMP = ".verified.json"
TIMEOUT = 10
FILE_MAX = 2 * 1024 * 1024
SKIP_DIRS = {"__pycache__", ".git"}

# import してよい物（標準ライブラリの計算・文字・データの道具と、同じ skill の中のファイル）
ALLOWED_IMPORTS = {
    "__future__", "math", "cmath", "statistics", "fractions", "decimal", "numbers", "random",
    "json", "csv", "argparse", "sys", "pathlib", "re", "string", "textwrap", "unicodedata",
    "dataclasses", "typing", "enum", "abc", "functools", "itertools", "operator", "collections",
    "copy", "bisect", "heapq", "datetime",
}
OPTIONAL_IMPORTS = {"numpy"}          # PC に入っていれば使える（SKILL.md に書くこと）
BANNED_CALLS = {"eval", "exec", "compile", "__import__", "breakpoint", "input"}
BANNED_ATTRS = {"system", "popen", "remove", "unlink", "rmdir", "removedirs", "rename", "rmtree",
                "write_text", "write_bytes", "mkdir", "makedirs", "chmod", "kill", "startfile", "spawnl", "execv"}


def _files(d: Path) -> list[Path]:
    out = []
    for p in sorted(d.rglob("*")):
        rel = p.relative_to(d)
        if p.is_file() and not any(part in SKIP_DIRS or part.startswith(".") for part in rel.parts):
            out.append(p)
    return out


def digest(d: Path) -> str:
    h = hashlib.sha256()
    for p in _files(d):
        h.update(p.relative_to(d).as_posix().encode("utf-8") + b"\0")
        h.update(p.read_bytes() + b"\0")
    return h.hexdigest()


def _front(text: str) -> dict:
    """SKILL.md の先頭（--- の間）の name / description だけを読む。"""
    m = re.match(r"^﻿?---\s*\n(.*?)\n---\s*(\n|$)", text, re.S)
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        k = re.match(r"^(name|description)\s*:\s*(.*)$", line)
        if k:
            v = k.group(2).strip()
            if v[:1] == '"':
                try:
                    v = json.loads(v)
                except json.JSONDecodeError:
                    v = v.strip('"')
            elif v[:1] == "'":
                v = v.strip("'")
            out[k.group(1)] = v
    return out


def scan_python(text: str, local: set[str]) -> tuple[list[str], list[str]]:
    """(止める理由, 気をつける事)。local は同じ skill の中のモジュール名（calc など）。"""
    errors, warns = [], []
    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        return [f"文法の誤り（{e.lineno} 行目）: {e.msg}"], []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            if isinstance(node, ast.ImportFrom) and node.level:
                continue                                   # from . import x（同じ skill の中）
            for n in names:
                top = n.split(".")[0]
                if top in ALLOWED_IMPORTS or top in local:
                    continue
                if top in OPTIONAL_IMPORTS:
                    warns.append(f"{top} を使う（PC に入っていないと動かない）")
                    continue
                errors.append(f"{node.lineno} 行目: import {n} は使えません（ネット・外部コマンド・ファイル操作を避けるため）")
        elif isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name) and f.id in BANNED_CALLS:
                errors.append(f"{node.lineno} 行目: {f.id}() は使えません")
            elif isinstance(f, ast.Attribute) and f.attr in BANNED_ATTRS:
                errors.append(f"{node.lineno} 行目: .{f.attr}() は使えません（ファイルを書く・消す・外部コマンド）")
            elif isinstance(f, ast.Name) and f.id == "open":
                mode = node.args[1] if len(node.args) > 1 else next((k.value for k in node.keywords if k.arg == "mode"), None)
                if mode is not None and not (isinstance(mode, ast.Constant) and isinstance(mode.value, str) and set(mode.value) <= set("rbt")):
                    errors.append(f"{node.lineno} 行目: open() は読むだけにしてください（mode が 'r' 以外）")
        elif isinstance(node, ast.Attribute) and node.attr in ("__subclasses__", "__globals__", "__builtins__", "__code__"):
            errors.append(f"{node.lineno} 行目: {node.attr} は使えません")
    return errors, warns


def lint(d: Path) -> dict:
    """動かさずに分かる問題。errors があれば検算しない。"""
    errors, warns = [], []
    name = d.name
    if not NAME_RE.match(name) or len(name) > 64:
        errors.append(f"skill の名前は英小文字・数字・ハイフン（64 字まで）: {name}")
    for r in REQUIRED:
        if not (d / r).is_file():
            errors.append(f"{r} がありません")
    files = _files(d)
    for p in files:
        if p.stat().st_size > FILE_MAX:
            errors.append(f"{p.relative_to(d).as_posix()} が大きすぎます（2MB まで）")
    sk = d / "SKILL.md"
    if sk.is_file():
        fm = _front(sk.read_text(encoding="utf-8", errors="replace"))
        if not fm:
            errors.append("SKILL.md の先頭に --- で囲んだ name と description がありません")
        else:
            if fm.get("name") != name:
                errors.append(f"SKILL.md の name（{fm.get('name', '')}）とフォルダの名前（{name}）が違います")
            desc = fm.get("description", "")
            if not desc.strip() or desc.startswith("（"):
                errors.append("SKILL.md の description が空か、ひな形のままです")
            elif len(desc) > 1024:
                errors.append(f"description が長すぎます（{len(desc)} 字。1024 字まで）")
        body = sk.read_text(encoding="utf-8", errors="replace")
        if "（ここに出典" in body or "（著者 年" in body:
            warns.append("SKILL.md に出典がまだ書かれていません")
    ex = d / "examples.json"
    if ex.is_file():
        try:
            cases = json.loads(ex.read_text(encoding="utf-8")).get("cases")
            if not isinstance(cases, list) or not cases:
                errors.append("examples.json に cases（検算の値）がありません")
            elif any("ひな形" in str(c.get("name", "")) for c in cases):
                warns.append("examples.json がひな形の値のままです（論文の表・図の値に置き換える）")
        except (json.JSONDecodeError, AttributeError) as e:
            errors.append(f"examples.json が JSON として読めません: {e}")
    local = {p.stem for p in files if p.suffix == ".py"}
    for p in files:
        if p.suffix == ".py":
            e, w = scan_python(p.read_text(encoding="utf-8", errors="replace"), local)
            rel = p.relative_to(d).as_posix()
            errors += [f"{rel}: {x}" for x in e]
            warns += [f"{rel}: {x}" for x in dict.fromkeys(w)]
        elif p.suffix.lower() not in (".md", ".json", ".csv", ".txt"):
            warns.append(f"{p.relative_to(d).as_posix()}: 見ていない種類のファイル")
    if "（ここに出典" in ((d / "scripts" / "calc.py").read_text(encoding="utf-8", errors="replace") if (d / "scripts" / "calc.py").is_file() else ""):
        warns.append("calc.py の SOURCE（出典）がひな形のままです")
    return {"errors": errors, "warnings": warns}


def _python() -> str:
    return sys.executable.replace("pythonw.exe", "python.exe")


def _run(d: Path, args: list[str]) -> dict:
    env = {k: v for k, v in os.environ.items() if k.upper() in ("SYSTEMROOT", "TEMP", "TMP", "PATH", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA")}
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    t0 = time.monotonic()
    try:
        r = subprocess.run([_python(), "-E", "-B", *args], cwd=str(d), env=env, capture_output=True, timeout=TIMEOUT,
                           stdin=subprocess.DEVNULL, creationflags=0x08000000 if os.name == "nt" else 0)
    except subprocess.TimeoutExpired:
        return {"error": f"{TIMEOUT} 秒で終わらなかったので止めました"}
    ms = int((time.monotonic() - t0) * 1000)
    out = r.stdout.decode("utf-8", errors="replace").strip()
    err = r.stderr.decode("utf-8", errors="replace").strip()
    try:
        data = json.loads(out.splitlines()[-1]) if out else None
    except json.JSONDecodeError:
        data = None
    if not isinstance(data, dict):
        return {"error": "結果が JSON ではありません", "stdout": out[-2000:], "stderr": err[-2000:], "ms": ms}
    return {"data": data, "stderr": err[-2000:], "ms": ms, "code": r.returncode}


def run(d: Path) -> dict:
    """検算: calc.py を 1 回（examples の 1 件目）、check.py を examples.json で。合えば .verified.json を残す。"""
    li = lint(d)
    if li["errors"]:
        return {"ok": False, "stage": "lint", **li}
    cases = json.loads((d / "examples.json").read_text(encoding="utf-8"))["cases"]
    calc = _run(d, ["scripts/calc.py", "--json", json.dumps(cases[0].get("inputs", {}), ensure_ascii=False)])
    if "error" in calc or "error" in calc.get("data", {}):
        return {"ok": False, "stage": "calc", "calc": calc, **li}
    chk = _run(d, ["scripts/check.py", "--file", "examples.json"])
    if "error" in chk or "error" in chk.get("data", {}):
        return {"ok": False, "stage": "check", "calc": calc, "check": chk, **li}
    ok = bool(chk["data"].get("pass"))
    res = {"ok": ok, "stage": "done", "calc": calc, "check": chk, **li}
    stamp = d / STAMP
    if ok:
        stamp.write_text(json.dumps({"digest": digest(d), "at": time.strftime("%Y-%m-%d %H:%M"),
                                     "summary": chk["data"].get("summary")}, ensure_ascii=False), encoding="utf-8")
    elif stamp.exists():
        stamp.unlink()
    return res


def status(d: Path) -> dict:
    """検算済みで、その後に中身が変わっていないか。"""
    s = d / STAMP
    if not s.is_file():
        return {"verified": False, "at": "", "changed": False}
    try:
        st = json.loads(s.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"verified": False, "at": "", "changed": False}
    same = st.get("digest") == digest(d)
    return {"verified": same, "at": st.get("at", ""), "changed": not same, "summary": st.get("summary")}


def make_zip(d: Path, out_dir: Path) -> Path:
    """<名前>.zip（中は <名前>/SKILL.md …）。検算済みでなければ ValueError。上書きしない。"""
    if not status(d)["verified"]:
        raise ValueError("検算が済んでいないか、検算の後に中身が変わりました。先に検算してください")
    out_dir.mkdir(parents=True, exist_ok=True)
    z = out_dir / f"{d.name}.zip"
    i = 2
    while z.exists():
        z = out_dir / f"{d.name} ({i}).zip"
        i += 1
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in _files(d):
            zf.write(p, f"{d.name}/{p.relative_to(d).as_posix()}")
    return z
