"""lab/cards.py — 論文のカード（md）の front matter を読み書きする。標準ライブラリだけ。

・front matter は YAML の小さな部分だけを使う（LAB_FORMAT.md に書いた形）:
    key: "文字"   key: 2024   key: [a, "b c"]   key: 文字（引用符なし）
    key:            ← 次の行から「  - 項目」の一覧（Claude が書いても読めるように）
・知らないキーは消さずに残す（書き戻すときも同じ順番）
・本文（front matter の後ろ）はそのまま。Lab Sketch は本文を書き換えない
"""
from __future__ import annotations

import json
import re

STATUSES = ("unread", "read", "cite")
LIST_KEYS = ("authors", "tags", "skills")
ORDER = ("title", "authors", "year", "doi", "pdf", "source", "tags", "status", "skills", "added")

SECTIONS = {
    "ja": ("要約", "手法", "結論", "式・数値（エンジンの元）", "自分のメモ"),
    "en": ("Summary", "Method", "Conclusions", "Equations & values (engine source)", "My notes"),
}

_KEY = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:(.*)$")


class CardError(Exception):
    pass


def _scalar(s: str):
    s = s.strip()
    if not s:
        return ""
    if s[0] == '"':
        try:
            return json.loads(s[: _close_quote(s) + 1])
        except (ValueError, json.JSONDecodeError):
            raise CardError(f"引用符が閉じていません: {s}")
    if s[0] == "'":
        end = s.find("'", 1)
        if end < 0:
            raise CardError(f"引用符が閉じていません: {s}")
        return s[1:end]
    s = re.split(r"\s+#", s, maxsplit=1)[0].strip()       # 引用符なしの値の後ろの # はコメント
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    return s


def _close_quote(s: str) -> int:
    i = 1
    while i < len(s):
        if s[i] == "\\":
            i += 2
            continue
        if s[i] == '"':
            return i
        i += 1
    raise ValueError


def _flow_list(s: str) -> list:
    end = s.rfind("]")                            # 閉じかっこの後ろ（# コメント）は捨てる
    if end < 0:
        raise CardError(f"[ ] が閉じていません: {s}")
    s = s[: end + 1].strip()
    try:
        v = json.loads(s)
        if isinstance(v, list):
            return v
    except json.JSONDecodeError:
        pass
    out, cur, q = [], "", None                    # [a, "b, c", 'd'] を手で分ける
    for ch in s[1:-1]:
        if q:
            cur += ch
            if ch == q:
                q = None
        elif ch in "\"'":
            q = ch
            cur += ch
        elif ch == ",":
            out.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur)
    return [_scalar(x) for x in out if x.strip()]


def split(text: str) -> tuple[str | None, str]:
    """(front matter の中身 or None, 本文)。"""
    text = text.lstrip("﻿")
    m = re.match(r"^---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|$)", text, re.S)
    if not m:
        return None, text
    return m.group(1), text[m.end():]


def parse(text: str) -> tuple[dict, str]:
    """カードの md → (meta, 本文)。読めない行があれば CardError（何行目か）。"""
    fm, body = split(text)
    meta: dict = {}
    if fm is None:
        return meta, body
    key = None
    for n, raw in enumerate(fm.splitlines(), 2):
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        item = re.match(r"^\s+-\s*(.*)$", line) or re.match(r"^-\s+(.*)$", line)
        if item and key is not None and isinstance(meta.get(key), list):
            meta[key].append(_scalar(item.group(1)))
            continue
        m = _KEY.match(line)
        if not m:
            raise CardError(f"front matter の {n} 行目が読めません: {line.strip()}")
        key, val = m.group(1), m.group(2).strip()
        try:
            if not val:
                meta[key] = []                     # 次の行から「- 項目」（無ければ空）
            elif val.startswith("["):
                meta[key] = _flow_list(val)
            else:
                meta[key] = _scalar(val)
        except CardError as e:
            raise CardError(f"front matter の {n} 行目: {e}")
    for k in ("title", "doi", "pdf", "source", "status", "added"):
        if meta.get(k) == []:
            meta[k] = ""
    return meta, body


def normalize(meta: dict) -> dict:
    """画面と一覧で使う形に揃える（足りない項目は空）。知らないキーは残す。"""
    m = dict(meta)
    for k in LIST_KEYS:
        v = m.get(k, [])
        if isinstance(v, str):
            v = re.split(r"[;；、\n]" if k == "authors" else r"[,，、;；\n]", v)   # 著者は「Smith, J.」があるのでカンマで分けない
        m[k] = [str(x).strip() for x in (v or []) if str(x).strip()]
    y = m.get("year", "")
    m["year"] = y if isinstance(y, int) else (int(y) if str(y).strip().isdigit() else "")
    for k in ("title", "doi", "pdf", "source", "added"):
        m[k] = str(m.get(k, "") or "").strip()
    st = str(m.get("status", "") or "").strip().lower()
    m["status"] = st if st in STATUSES else "unread"
    return m


def _val(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, list):
        return json.dumps([x if isinstance(x, int) else str(x) for x in v], ensure_ascii=False)
    return json.dumps(str(v), ensure_ascii=False)


def dump(meta: dict, body: str) -> str:
    keys = [k for k in ORDER if k in meta] + [k for k in meta if k not in ORDER]
    lines = ["---"]
    for k in keys:
        v = meta[k]
        if k == "status":
            lines.append(f"status: {v}")
        elif k == "added" and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(v)):
            lines.append(f"added: {v}")
        else:
            lines.append(f"{k}: {_val(v)}")
    lines.append("---")
    return "\n".join(lines) + "\n" + body.lstrip("\r\n")


def new_body(lang: str = "ja") -> str:
    return "\n" + "\n\n".join(f"## {h}\n" for h in SECTIONS.get(lang, SECTIONS["ja"]))


def filled(body: str) -> list[str]:
    """本文の中で、中身が書いてある節の見出し（一覧で「まとめ済み」を出すため）。"""
    out = []
    for m in re.finditer(r"^##\s+(.+?)\s*$([\s\S]*?)(?=^##\s|\Z)", body, re.M):
        if m.group(2).strip():
            out.append(m.group(1))
    return out
